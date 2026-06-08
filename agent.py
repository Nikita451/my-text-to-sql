from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

import os
import json
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langfuse.callback import CallbackHandler
import uuid
from config.db import fastembed_executor

from agent_graph import app
from state import AgentState
from langfuse.decorators import observe, langfuse_context
from config.db import async_qdrant_client
from config.db_manager import pool_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    yield  # В этой точке сервер FastAPI стартует и начинает слушать порт 8000
    
    # 2. КОД ПРИ ВЫКЛЮЧЕНИИ СЕРВЕРА
    print("⏳ [LIFESPAN]: Закрываем пулы соединений и фоновых потоков...")
    await pool_manager.close_all_pools()

    await async_qdrant_client.close() 
    print("✅ [LIFESPAN]: Сессия Qdrant успешно закрыта.")
    
    # Флаг wait=False важен для reload=True, чтобы uvicorn не зависал при перезапуске кода
    fastembed_executor.shutdown(wait=False) 
    print("🛑 [LIFESPAN]: Все пулы успешно остановлены. Сервер выключен.")


# Описываем структуру входящего запроса от фронтэнда
class ChatRequest(BaseModel):
    message: str = Field(..., description="Текстовый вопрос пользователя к базе данных")
    thread_id: str = Field("default_web_thread", description="Идентификатор сессии для работы памяти диалога")

app_fastapi = FastAPI(
    lifespan=lifespan,
    title="AI SQL Analyst API",
    description="Backend API для мультиагентного Text-to-SQL ассистента",
    version="1.0.0"
)

# НАСТРОЙКА CORS: разрешаем фронтэнду (Next.js) отправлять запросы
app_fastapi.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    

@app_fastapi.post("/api/chat")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    """Эндпоинт для отправки сообщений агенту со стримингом процесса размышлений."""
    col_name = "vasya"
    db_name  = "vasya"
    return StreamingResponse(
        run_agent_stream(request.message, request.thread_id, col_name=col_name, db_name=db_name),
        media_type="text/event-stream"
    )

@app_fastapi.get("/")
def read_root():
    return {"status": "ok", "message": "FastAPI works 787878!"}


if __name__ == "__main__":
    import uvicorn
    # Запускаем локальный веб-сервер на порту 8000
    uvicorn.run("agent:app_fastapi", host="0.0.0.0", port=8000, reload=True)



