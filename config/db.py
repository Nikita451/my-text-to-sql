# db.py
from psycopg_pool import AsyncConnectionPool
from concurrent.futures import ThreadPoolExecutor
import os
from config.common_config import settings

from qdrant_client import AsyncQdrantClient


# 1. Создаем кастомный пул потоков операционной системы при старте приложения
# max_workers=4 означает, что внутри ОС будет создано ровно 4 "рабочих" потока.
# Сколько бы запросов ни пришло, FastEmbed не займет больше 4 потоков процессора.
# Преимущество над asyncio.to_thread - мы контролируем число потоков. 
fastembed_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="FastEmbed")

# Пулы под капотом будут созданы автоматом
async_qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)
