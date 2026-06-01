from typing import Any, Dict, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from psycopg import logger
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

ROUTER_SYSTEM_PROMPT = """Вы — главный диспетчер аналитической системы. Ваша задача — проанализировать последнее сообщение пользователя и выбрать идеального следующего исполнителя.

ТЕКУЩИЙ КОНТЕКСТ ЗНАНИЙ О БАЗЕ ДАННЫХ (схемы таблиц):
===
{context}
===

ПРАВИЛА ВЫБОРА (СТРОГИЙ ПРИОРИТЕТ):
1. Если ТЕКУЩИЙ КОНТЕКСТ ЗНАНИЙ пуст (написано "Контекст пуст"), вы ОБЯЗАНЫ выбрать 'qdrant_rag'. Вы не имеете права отправлять задачу к 'sql_coder', если у него нет схем таблиц!
2. Если в контексте уже есть схемы таблиц, но для ответа на новый вопрос пользователя нужны новые таблицы, которых нет в контексте — выбирайте 'qdrant_rag'.
3. Если в контексте уже есть схемы нужных таблиц, и нужно написать или выполнить SQL-запрос к PostgreSQL — выбирайте 'sql_coder'.
4. Если из базы данных уже вернулся успешный результат (сообщение со строкой "📊 [Данные из БД]"), и нужно просто вежливо ответить пользователю — выбирайте 'general_responder'.

Возвращайте ТОЛЬКО структурированный выбор.
"""

# Инициализируем модель роутера (строго temperature=0 для точной классификации)
router_llm = ChatOpenRouter(
    model=settings.model, 
    api_key=SecretStr(settings.openrouter_api_key),
    temperature=0
).with_structured_output(RouterDecision)


def router_node(state: AgentState) -> Command:
    """Узел-диспетчер: принимает решение на основе ИИ или жесткой Python-логики."""

    if state.get("sql_result"):
        print("🧠 [РОУТЕР (Python)]: Данные из Postgres уже в буфере. Направляю к: general_responder")
        return Command(goto="general_responder")
    
    messages = state["messages"]
    current_context = state.get("context", "").strip()
    # Проверяем, лежат ли уже данные из Postgres в состоянии
    has_sql_data = "Да" if state.get("sql_result") else "Нет"
    
    system_content = ROUTER_SYSTEM_PROMPT.format(
        context=current_context if current_context else "Контекст пуст. Схем таблиц нет."
    )
    
    system_content += f"\nДанные из SQL-базы уже получены: {has_sql_data}\n"
    system_content += "Если данные из SQL-базы уже получены (Да), ты ОБЯЗАН выбрать 'general_responder'."

    prompt = [SystemMessage(content=system_content)] + messages
    decision: RouterDecision = router_llm.invoke(prompt) # type: ignore
    
    print(f"🧠 [РОУТЕР]: {decision.reasoning} ➡️ Направляю к: {decision.next_agent}")
    return Command(goto=decision.next_agent)

