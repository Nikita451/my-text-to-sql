from dotenv import load_dotenv
load_dotenv()

from config.logger_config import setup_logging
import logging
setup_logging()
logger = logging.getLogger(__name__)

import sys
from config.common_config import settings
from contextlib import asynccontextmanager
from core.errors_handler import setup_exception_handlers
from core.fastembed_executor import close_fastembed_executors, init_fastembed_executors
from core.qdrant_client import close_qdrant_client, init_qdrant_client
from core.vector_models import init_vector_models
from api.v1.api import api_router
from utils.bootstrap_system import bootstrap_system
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.db_manager import pool_manager
import importlib.util


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_fastembed_executors()
    init_vector_models()
    init_qdrant_client()

    await bootstrap_system()

    yield  # В этой точке сервер FastAPI стартует и начинает слушать порт 8000
    
    # 2. КОД ПРИ ВЫКЛЮЧЕНИИ СЕРВЕРА
    logger.info("⏳ [LIFESPAN]: Закрываем пулы соединений и фоновых потоков...")
    await pool_manager.close_all_pools()

    await close_qdrant_client()
    logger.info("✅ [LIFESPAN]: Сессия Qdrant успешно закрыта.")
    
    close_fastembed_executors()
    logger.info("🛑 [LIFESPAN]: Все пулы успешно остановлены. Сервер выключен.")



app_fastapi = FastAPI(
    lifespan=lifespan,
    title="AI SQL Analyst API",
    description="Backend API для мультиагентного Text-to-SQL ассистента",
    version="1.0.0"
)

setup_exception_handlers(app_fastapi)

# НАСТРОЙКА CORS: разрешаем фронтэнду (Next.js) отправлять запросы
app_fastapi.add_middleware(
    CORSMiddleware,
    # allow_origins=[settings.origin],
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

app_fastapi.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    # Запускаем локальный веб-сервер на порту 8000
    uvicorn.run("agent:app_fastapi", host="0.0.0.0", port=8000, reload=True)



