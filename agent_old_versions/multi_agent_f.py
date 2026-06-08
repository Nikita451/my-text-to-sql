from types import ModuleType

from dotenv import load_dotenv
load_dotenv()

import os
from state import AgentState
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from agent_graph import app

from langfuse.callback import CallbackHandler

langfuse_callback = CallbackHandler()

if __name__ == "__main__":
    config = RunnableConfig(
        configurable={"thread_id": "agent_loop_thread"},
        recursion_limit=10,
        callbacks=[langfuse_callback],
        tags=["production", "cli_user"],
        metadata={
            "environment": "production",
            "langfuse_session_id": "agent_loop_thread",
            "langfuse_user_id": "cli_user",
            "langfuse_trace_name": "agent_loop_execution"
        }
    )
    
    # --- ШАГ 1: Вопрос по известным таблицам ---
    print("\n--- ВОПРОС 1 ---")
    input_1: AgentState = {
        "messages": [HumanMessage(content="Покажи email пользователей с максимальными тратами")],
        "context": "",
         "sql_result": "",
         "sql_query": "",
         "db_name": "mydb",
        "col_name": "db_metadata",
    }

    for event in app.stream(input_1, config=config, stream_mode="values"):
        pass # Запускаем стриминг для прогона всех внутренних петель графа
        
    final_messages = app.get_state(config).values["messages"]
    print(f"Робот: {final_messages[-1].content}\n")
    
    # --- ШАГ 2: Дополнительный вопрос
    print("--- ВОПРОС 2 (Уточняющий / Повторный RAG) ---")
    input_2: AgentState = {
        "messages": [HumanMessage(content="А сколько заказов сделал самый активный пользователь?")],
        "context": "",
        "sql_result": "",
        "sql_query": "",
        "db_name": "mydb",
        "col_name": "db_metadata",
    }

    for event in app.stream(input_2, config=config, stream_mode="values"):
        pass
        
    final_messages = app.get_state(config).values["messages"]
    print(f"Робот: {final_messages[-1].content}")


"""
--- ВОПРОС 1 ---
🧠 [РОУТЕР]: Текущий контекст пуст, и для выполнения запроса нужны схемы таблиц, которых нет в контексте. ➡️ Направляю к: qdrant_rag
📚 [АГЕНТ QDRANT]: Начинаю поиск DDL-схем и метаданных в базе знаний...
✅ [АГЕНТ QDRANT]: Контекст успешно обновлен. Найдено документов: 2
🧠 [РОУТЕР]: Для получения email пользователей с максимальными тратами необходимо выполнить SQL-запрос к базе данных, используя уже имеющиеся схемы таблиц. ➡️ Направляю к: sql_coder
💻 [АГЕНТ-ПРОГРАММИСТ]: Начинаю генерацию и выполнение SQL-запроса...
🤖 [АГЕНТ-ПРОГРАММИСТ]: Попытка 1 из 3...
📝 [АГЕНТ-ПРОГРАММИСТ]: Сгенерирован SQL: SELECT u.email FROM users u JOIN orders o ON u.id = o.user_id GROUP BY u.email ORDER BY SUM(o.amount) DESC LIMIT 1;
✅ [АГЕНТ-ПРОГРАММИСТ]: SQL-запрос успешно выполнен!
🧠 [РОУТЕР (Python)]: Данные из Postgres уже в буфере. Направляю к: general_responder
✍️ [АГЕНТ-КОПИРАЙТЕР]: Стилизую ответ для пользователя...
Робот: Пользователь с максимальными тратами имеет следующий адрес электронной почты: **charlie@example.com**.

--- ВОПРОС 2 (Уточняющий / Повторный RAG) ---
🧠 [РОУТЕР]: Текущий контекст знаний пуст, поэтому необходимо выбрать 'qdrant_rag' для получения информации о самом активном пользователе. ➡️ Направляю к: qdrant_rag
📚 [АГЕНТ QDRANT]: Начинаю поиск DDL-схем и метаданных в базе знаний...
✅ [АГЕНТ QDRANT]: Контекст успешно обновлен. Найдено документов: 2
🧠 [РОУТЕР]: В контексте уже есть схемы таблиц, но для ответа на новый вопрос пользователя нужны новые таблицы, которых нет в контексте. ➡️ Направляю к: qdrant_rag
📚 [АГЕНТ QDRANT]: Начинаю поиск DDL-схем и метаданных в базе знаний...
✅ [АГЕНТ QDRANT]: Контекст успешно обновлен. Найдено документов: 2
🧠 [РОУТЕР]: В контексте уже есть схемы таблиц, и нужно написать SQL-запрос к PostgreSQL для получения количества заказов самого активного пользователя. ➡️ Направляю к: sql_coder
💻 [АГЕНТ-ПРОГРАММИСТ]: Начинаю генерацию и выполнение SQL-запроса...
🤖 [АГЕНТ-ПРОГРАММИСТ]: Попытка 1 из 3...
📝 [АГЕНТ-ПРОГРАММИСТ]: Сгенерирован SQL: SELECT user_id, COUNT(*) AS order_count FROM orders GROUP BY user_id ORDER BY order_count DESC LIMIT 1;
✅ [АГЕНТ-ПРОГРАММИСТ]: SQL-запрос успешно выполнен!
🧠 [РОУТЕР (Python)]: Данные из Postgres уже в буфере. Направляю к: general_responder
✍️ [АГЕНТ-КОПИРАЙТЕР]: Стилизую ответ для пользователя...
Робот: Самый активный пользователь (user_id: 3) сделал 2 заказа.
"""