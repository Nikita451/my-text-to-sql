# db.py
from typing import AsyncGenerator

from psycopg_pool import AsyncConnectionPool
from concurrent.futures import ThreadPoolExecutor
from config.common_config import settings

from qdrant_client import AsyncQdrantClient

BASE_CONN_STR = f"host={settings.pg_host} port={settings.pg_port} dbname=postgres user={settings.pg_user} password={settings.pg_password}"

# 1. Создаем кастомный пул потоков операционной системы при старте приложения
# max_workers=4 означает, что внутри ОС будет создано ровно 4 "рабочих" потока.
# Сколько бы запросов ни пришло, FastEmbed не займет больше 4 потоков процессора.
# Преимущество над asyncio.to_thread - мы контролируем число потоков. 
fastembed_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="FastEmbed")

# Пулы под капотом будут созданы автоматом
async_qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)

# async def get_qdrant_client() -> AsyncGenerator[AsyncQdrantClient, None]:
#     """Зависимость для внедрения асинхронного клиента Qdrant в эндпойнты."""
#     yield async_qdrant_client
