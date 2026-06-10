import json
import asyncio
from typing import AsyncGenerator
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langfuse.callback import CallbackHandler
import uuid
from agent_graph import app
from state import AgentState
from langfuse.decorators import langfuse_context


async def run_agent_stream(user_message: str, thread_id: str, col_name: str, db_name: str) -> AsyncGenerator[str, None]:
    """Асинхронный генератор, который запускает граф и стримит шаги работы агентов на фронтенд."""
    langfuse_callback = CallbackHandler()
    session_thread_id = thread_id or f"production_thread_{uuid.uuid4().hex[:8]}"
    config = RunnableConfig(
        configurable={"thread_id": session_thread_id},
        recursion_limit=10,
        callbacks=[langfuse_callback],
        tags=["production", "cli_user"],
        metadata={
            "environment": "production",
            "langfuse_session_id": session_thread_id,
            "langfuse_user_id": "cli_user",
            "langfuse_trace_name": "prod_loop_execution"
        }
    )
    
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_message)],
        "context": "",
         "sql_result": "",
         "sql_query": "",
         "col_name": col_name,
         "db_name": db_name
    }
    
    try:
        # Используем асинхронный метод .astream для построчного чтения шагов графа
        async for event in app.astream(initial_state, config=config, stream_mode="updates"):
            # event — это словарь вида {"имя_узла": {"messages": [...], "context": "..."}}
            for node_name, node_output in event.items():
                
                # Формируем технический статус для вывода красивого логгера на фронтэнде
                status_update = {
                    "type": "status",
                    "node": node_name,
                    "message": f"Агент {node_name} успешно завершил шаг."
                }
                
                if node_name == "router":
                    status_update["message"] = "🧠 Роутер анализирует контекст и выбирает исполнителя..."
                elif node_name == "qdrant_rag":
                    status_update["message"] = "📚 Библиотекарь извлекает схемы таблиц и Few-Shot примеры из Qdrant..."
                elif node_name == "sql_coder":
                    status_update["message"] = "💻 Программист генерирует оптимальный SQL и выполняет его в Postgres..."
                elif node_name == "general_responder":
                    status_update["message"] = "✍️ Копирайтер переводит сырые данные базы в человеческий ответ..."

                # Отправляем статус на фронтенд в формате SSE (строка с префиксом data:)
                yield f"data: {json.dumps(status_update, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1) # Минимальная пауза для стабильности потока
                
        state_data = await app.aget_state(config)
        final_messages = state_data.values.get("messages", [])
        
        if final_messages:
            final_text = final_messages[-1].content
            final_response = {
                "type": "final_answer",
                "content": str(final_text)
            }
            yield f"data: {json.dumps(final_response, ensure_ascii=False)}\n\n"
            
    except Exception as e:
        error_response = {
            "type": "error",
            "message": f"Произошла критическая ошибка в рантайме графа: {e}"
        }
        yield f"data: {json.dumps(error_response, ensure_ascii=False)}\n\n"
    finally:
        langfuse_context.flush()