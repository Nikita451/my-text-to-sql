from typing import Dict, Any, List, cast, LiteralString
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openrouter import ChatOpenRouter
import psycopg
from psycopg import sql
from pydantic import BaseModel, Field, SecretStr
from state import AgentState
import os
from config.common_config import settings
from langgraph.types import Command

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

CONN_STR = f"host={os.getenv('PG_HOST', 'localhost')} port={os.getenv('PG_PORT', '5432')} dbname={os.getenv('PG_DB', 'mydb')} user={os.getenv('PG_USER', 'myuser')} password={os.getenv('PG_PASSWORD', 'mypassword')}"

class GeneratedSQL(BaseModel):
    reasoning: str = Field(description="Логика рассуждения")
    sql_query: str = Field(description="Чистый SQL-запрос")

llm = ChatOpenRouter(
    model="openai/gpt-4o-mini", 
    api_key=SecretStr(settings.openrouter_api_key),
    temperature=0
)
sql_coder_llm = llm.with_structured_output(GeneratedSQL)

def sql_coder_node(state: AgentState) -> Command:
    """Узел-Программист: пишет SQL, выполняет в Postgres и сам чинит баги (до 3 попыток)."""
    print("💻 [АГЕНТ-ПРОГРАММИСТ]: Начинаю генерацию и выполнение SQL-запроса...")
    
    db_context = state.get("context", "")
    if not db_context:
        print("⚠️ [АГЕНТ-ПРОГРАММИСТ]: Контекст схем пуст! Безопасно возвращаю граф в Роутер.")
        return Command(goto="router")
    
    user_question = ""
    if state.get("messages"):
        # Идем по списку сообщений с конца к началу
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_question = str(msg.content)
                break
    if not user_question:
        print("⚠️ [АГЕНТ-ПРОГРАММИСТ]: Не удалось найти вопрос пользователя в истории!")
        return Command(goto="router")
    
    # Инициализируем историю сообщений для внутренней работы программиста
    coder_messages = [
        SystemMessage(content=SQL_CODER_SYSTEM_PROMPT.format(context=db_context)),
        HumanMessage(content=f"Напиши SQL-запрос для задачи: {user_question}")
    ]
    
    max_attempts = 3
    last_generated_query = ""
    
    for attempt in range(1, max_attempts + 1):
        print(f"🤖 [АГЕНТ-ПРОГРАММИСТ]: Попытка {attempt} из {max_attempts}...")
        
        # 1. Заставляем модель сгенерировать SQL по строгой схеме Pydantic
        response: GeneratedSQL = sql_coder_llm.invoke(coder_messages) # type: ignore
        last_generated_query = response.sql_query
        
        print(f"📝 [АГЕНТ-ПРОГРАММИСТ]: Сгенерирован SQL: {last_generated_query}")
        
        # 2. Пытаемся выполнить его в PostgreSQL
        try:
            with psycopg.connect(CONN_STR) as conn:
                with conn.cursor() as cur:
                    safe_query = cast(LiteralString, last_generated_query)
                    cur.execute(safe_query)
                    
                    colnames = [desc.name for desc in cur.description] if cur.description else []
                    rows = cur.fetchall() if cur.description else []
                    
                    # Если всё выполнилось успешно, собираем результат в строку и выходим из цикла!
                    sql_result_str = f"Колонки: {colnames}\nСтроки:\n" + "\n".join([str(row) for row in rows])
                    print("✅ [АГЕНТ-ПРОГРАММИСТ]: SQL-запрос успешно выполнен!")
                    
                    # Возвращаем результат. Роутер увидит это сообщение и поймет, что данные собраны
                    return Command(
                        goto="router",
                        update={
                            "sql_query": safe_query,
                            "sql_result": sql_result_str
                        }
                    )
                    
        except Exception as pg_error:
            print(f"❌ [АГЕНТ-ПРОГРАММИСТ]: Postgres вернул ошибку: {pg_error}")
            
            # Если попытки ещё есть, дописываем ошибку в локальный контекст программиста и идем на новый круг!
            if attempt < max_attempts:
                coder_messages.append(AIMessage(content=f"Мой прошлый запрос: {last_generated_query}"))
                coder_messages.append(HumanMessage(
                    content=f"⚠️ База данных вернула ошибку:\n{pg_error}\nПроанализируй её, найди баг в именах полей или синтаксисе и напиши ИСПРАВЛЕННЫЙ SQL-запрос."
                ))
            else:
                # Если все 3 попытки исчерпаны, сдаемся и возвращаем лог ошибки Роутеру
                print("🛑 [АГЕНТ-ПРОГРАММИСТ]: Не удалось исправить SQL за 3 попытки.")
                print(f"Ошибка выполнения SQL после {max_attempts} попыток. Лог: {pg_error}")
                return Command(goto="router")
    
    print(f"Неизвестная ошибка в узле программиста.")
    return Command(goto="router")

