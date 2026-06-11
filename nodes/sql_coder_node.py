import logging
from typing import cast, LiteralString
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, Field, SecretStr
from state import AgentState
from config.common_config import settings
from langgraph.types import Command
from config.db_manager import pool_manager

logger = logging.getLogger(__name__)

SQL_CODER_SYSTEM_PROMPT = """Вы — изолированный ИИ-модуль, отвечающий за написание и исправление SQL-запросов для PostgreSQL.

Ваша единственная задача — сгенерировать валидный SQL-запрос на основе вопроса пользователя и предоставленных схем таблиц.

ДОСТУПНЫЕ СХЕМЫ ТАБЛИЦ:
===
{context}
===

ПРАВИЛА:
1. Используйте ТОЛЬКО таблицы и колонки из предоставленных схем.
2. Возвращайте строго валидный JSON-объект, соответствующий схеме.
3. Пишите чистый SQL без markdown-разметки (без ```sql).
"""

class GeneratedSQL(BaseModel):
    reasoning: str = Field(description="Логика рассуждения")
    sql_query: str = Field(description="Чистый SQL-запрос")

base_llm = ChatOpenRouter(
    model=settings.model, 
    api_key=SecretStr(settings.openrouter_api_key),
    temperature=0
).with_structured_output(GeneratedSQL)

sql_coder_llm = base_llm.with_retry(
    stop_after_attempt=3,
    retry_if_exception_type=(Exception, ValueError),
    wait_exponential_jitter=True # делает паузы между попытками чуть-чуть случайными
)

async def sql_coder_node(state: AgentState) -> Command:
    """Узел-Программист: пишет SQL, выполняет в Postgres и сам чинит баги (до 3 попыток)."""
    logger.info("💻 [АГЕНТ-ПРОГРАММИСТ]: Начинаю генерацию и выполнение SQL-запроса...")
    
    db_context = state.get("context", "")
    if not db_context:
        logger.warning("⚠️ [АГЕНТ-ПРОГРАММИСТ]: Контекст схем пуст! Безопасно возвращаю граф в Роутер.")
        return Command(goto="router")
    
    user_question = ""
    if state.get("messages"):
        # Идем по списку сообщений с конца к началу
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_question = str(msg.content)
                break
    if not user_question:
        logger.warning("⚠️ [АГЕНТ-ПРОГРАММИСТ]: Не удалось найти вопрос пользователя в истории!")
        return Command(goto="router")
    
    # Инициализируем историю сообщений для внутренней работы программиста
    coder_messages = [
        SystemMessage(content=SQL_CODER_SYSTEM_PROMPT.format(context=db_context)),
        HumanMessage(content=f"Напиши SQL-запрос для задачи: {user_question}")
    ]
    
    max_attempts = 4
    last_generated_query = ""
    db_name = state["db_name"]
    db_pool = await pool_manager.get_pool(db_name)
    
    for attempt in range(1, max_attempts + 1):
        logger.info(f"🤖 [АГЕНТ-ПРОГРАММИСТ]: Попытка {attempt} из {max_attempts}...")
        
        # 1. Заставляем модель сгенерировать SQL по строгой схеме Pydantic
        response: GeneratedSQL = await sql_coder_llm.ainvoke(coder_messages) # type: ignore
        if response is None:
            logger.warning(f"⚠️ Модель вернула None или не смогла распарсить JSON на попытке {attempt}.")
            coder_messages.append(HumanMessage(
                content=f"⚠️ Ошибка: Твой прошлый ответ не соответствовал JSON-схеме Pydantic или был пуст. Пожалуйста, строго следуй формату и не пиши лишнего текста."
            ))
            continue

        last_generated_query = response.sql_query
        
        logger.info(f"📝 [АГЕНТ-ПРОГРАММИСТ]: Сгенерирован SQL: {last_generated_query}")
        
        # 2. Пытаемся выполнить его в PostgreSQL
        try:
            async with db_pool.connection() as conn:  
                async with conn.cursor() as cur:
                    safe_query = cast(LiteralString, last_generated_query)
                    await cur.execute(safe_query)
                    
                    colnames = [desc.name for desc in cur.description] if cur.description else []
                    rows = await cur.fetchall() if cur.description else []
                    
                    # Если всё выполнилось успешно, собираем результат в строку и выходим из цикла!
                    sql_result_str = f"Колонки: {colnames}\nСтроки:\n" + "\n".join([str(row) for row in rows])
                    logger.info("✅ [АГЕНТ-ПРОГРАММИСТ]: SQL-запрос успешно выполнен!")
                    
                    # Возвращаем результат. Роутер увидит это сообщение и поймет, что данные собраны
                    return Command(
                        goto="router",
                        update={
                            "sql_query": safe_query,
                            "sql_result": sql_result_str
                        }
                    )
                    
        except Exception as pg_error:
            logger.error(f"❌ [АГЕНТ-ПРОГРАММИСТ]: Postgres вернул ошибку: {pg_error}")
            
            # Если попытки ещё есть, дописываем ошибку в локальный контекст программиста и идем на новый круг!
            if attempt < max_attempts:
                coder_messages.append(AIMessage(content=f"Мой прошлый запрос: {last_generated_query}"))
                coder_messages.append(HumanMessage(
                    content=f"⚠️ База данных вернула ошибку:\n{pg_error}\nПроанализируй её, найди баг в именах полей или синтаксисе и напиши ИСПРАВЛЕННЫЙ SQL-запрос."
                ))
            else:
                # Если все 3 попытки исчерпаны, сдаемся и возвращаем лог ошибки Роутеру
                logger.error("🛑 [АГЕНТ-ПРОГРАММИСТ]: Не удалось исправить SQL за 3 попытки.")
                logger.error(f"Ошибка выполнения SQL после {max_attempts} попыток. Лог: {pg_error}")
                return Command(goto="router")
    
    logger.error(f"Неизвестная ошибка в узле программиста.")
    return Command(goto="router")

