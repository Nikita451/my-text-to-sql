import logging
from typing import Any, Dict, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from state import AgentState
from config.common_config import settings
from pydantic import BaseModel, Field
from langchain_openrouter import ChatOpenRouter
from pydantic import SecretStr
from langgraph.types import Command

class RouterDecision(BaseModel):
    reasoning: str = Field(description="Краткое объяснение: почему выбран именно этот шаг")
    next_agent: Literal["qdrant_rag", "sql_coder", "general_responder"] = Field(
        description="Имя следующего агента, которому нужно передать управление"
    )

ROUTER_SYSTEM_PROMPT = """Ты — главный диспетчер аналитической системы. Твоя единственная задача — проанализировать последнее сообщение пользователя, оценить текущее состояние данных и выбрать имя следующего исполнителя (ноды).

ТЕКУЩЕЕ СОСТОЯНИЕ СИСТЕМЫ:
- Наличие контекста знаний (схемы таблиц): {has_context}
- Наличие результата из базы данных (SQL результат): {has_sql_result}

СПРАВОЧНЫЙ КОНТЕКСТ ЗНАНИЙ (СХЕМЫ ТАБЛИЦ ИЗ QDRANT):
===
{context}
===

ПРАВИЛА И ПРИОРИТЕТЫ ДЛЯ ВЫБОРА:
1. Если Наличие контекста знаний = 'НЕТ' (или написано "Контекст пуст"), ты ОБЯЗАН выбрать 'qdrant_rag'. Без схем таблиц отправлять задачу дальше нельзя!
2. Если контекст знаний есть, но для ответа на новый вопрос пользователя нужны другие таблицы, которых в контексте сейчас нет — выбирай 'qdrant_rag'.
3. Если Наличие результата из базы данных = 'ДА' — это значит, что SQL-запрос уже выполнен. Твоя задача завершена, выбирай 'general_responder' для формирования финального ответа.
4. Во всех остальных случаях, когда схемы нужных таблиц уже есть в контексте и нужно написать или выполнить SQL-запрос к PostgreSQL — выбирай 'sql_coder'.
"""


logger = logging.getLogger(__name__)

# Инициализируем модель роутера (строго temperature=0 для точной классификации)
base_llm = ChatOpenRouter(
    model=settings.model, 
    api_key=SecretStr(settings.openrouter_api_key),
    temperature=0
).with_structured_output(RouterDecision)

router_llm = base_llm.with_retry(
    stop_after_attempt=3,
    # Указываем список ошибок. LangChain сам перехватит и сетевые сбои, 
    # и наш ручной ValueError, если модель вернет пустой None.
    retry_if_exception_type=(Exception, ValueError),
    wait_exponential_jitter=True # делает паузы между попытками чуть-чуть случайными
)

async def router_node(state: AgentState) -> Command:
    """Узел-диспетчер: принимает решение на основе ИИ или жесткой Python-логики."""

    if state.get("sql_result"):
        logger.info("🧠 [РОУТЕР (Python)]: Данные из Postgres уже в буфере. Направляю к: general_responder")
        return Command(goto="general_responder")
    
    messages = state["messages"]
    current_context = state.get("context", "").strip()
    has_context = "ДА" if (current_context and "Контекст пуст" not in current_context) else "НЕТ"
    # Проверяем, лежат ли уже данные из Postgres в состоянии
    has_sql_data = "Да" if state.get("sql_result") else "Нет"

    # Безопасное экранирование скобок в контексте
    safe_context = current_context.replace("{", "{{").replace("}", "}}")
    
    # system_content = ROUTER_SYSTEM_PROMPT.format(
    #     context=current_context if current_context else "Контекст пуст. Схем таблиц нет."
    # )
    system_content = ROUTER_SYSTEM_PROMPT.format(
        has_context=has_context,
        has_sql_result=has_sql_data,
        context=safe_context
    )
    
    system_content += f"\nДанные из SQL-базы уже получены: {has_sql_data}\n"
    system_content += "Если данные из SQL-базы уже получены (Да), ты ОБЯЗАН выбрать 'general_responder'."

    prompt = [SystemMessage(content=system_content)] + messages

    try:
        decision: RouterDecision = await router_llm.ainvoke(prompt) # type: ignore
        if decision and getattr(decision, 'next_node', None):
            logger.info("🧠 [РОУТЕР]: %s ➡️ Направляю к: %s", decision.reasoning, decision.next_agent)
            return Command(goto=decision.next_agent)
        raise ValueError("Empty response from LLM")
    except Exception as e:
        # 3. ЕСЛИ ИИ СБОИТ: Включаем каскадный спасательный круг на основе State
        logging.warning(f"⚠️ Роутер сбоил ({str(e)}). Включаю каскадную защиту.")
        
        # Сценарий А: Данные из базы данных УЖЕ ЕСТЬ в стейте. 
        # Ведем напрямую в финальный ответ, чтобы не потерять результат запроса.
        sql_res = state.get("sql_result")
        if sql_res is not None and sql_res.strip() != "":
            logging.info("Резервный путь: [sql_result найден] ➔ Принудительно идем в general_responder")
            return Command(goto="general_responder")
            
        # Сценарий Б: Данных из БД еще нет, но схемы таблиц в контексте уже собраны.
        # Ведем напрямую в генератор SQL-кода.
        elif safe_context and safe_context.strip() != "" and "Контекст пуст" not in safe_context:
            logging.info("Резервный путь: [Схемы таблиц есть] ➔ Принудительно идем в sql_coder")
            return Command(goto="sql_coder")
            
        # Сценарий В: Полный холодный старт, в стейте вообще ничего нет.
        # Ведем в Qdrant собирать контекст знаний о таблицах.
        else:
            logging.info("Резервный путь: [Стейт пуст] ➔ Принудительно идем в qdrant_rag")
            return Command(goto="qdrant_rag")


