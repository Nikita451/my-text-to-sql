# db.py
from psycopg_pool import AsyncConnectionPool
from concurrent.futures import ThreadPoolExecutor
import os
from config.common_config import settings

from qdrant_client import AsyncQdrantClient

CONN_STR = f"host={os.getenv('PG_HOST', 'localhost')} port={os.getenv('PG_PORT', '5432')} dbname={os.getenv('PG_DB', 'mydb')} user={os.getenv('PG_USER', 'myuser')} password={os.getenv('PG_PASSWORD', 'mypassword')}"
# Глобальные объекты (пока не запущены)
db_pool = AsyncConnectionPool(
    conninfo=CONN_STR,
    min_size=2,
    max_size=10,
    open=False  # Важно: откроем в main.py
)

# 1. Создаем кастомный пул потоков операционной системы при старте приложения
# max_workers=2 означает, что внутри ОС будет создано ровно 4 "рабочих" потока.
# Сколько бы запросов ни пришло, FastEmbed не займет больше 4 потоков процессора.
# Преимущество над asyncio.to_thread - мы контролируем число потоков. 
fastembed_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="FastEmbed")

# Пулы под капотом будут созданы автоматом
async_qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)
