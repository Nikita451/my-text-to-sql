import logging
from typing import Dict
from psycopg import AsyncConnection
from psycopg.rows import TupleRow
from psycopg_pool import AsyncConnectionPool
from config.common_config import settings

logger = logging.getLogger(__name__)

class DynamicPoolManager:
    def __init__(self):
        # Хранилище пулов в формате { "имя_бд": AsyncConnectionPool }
        # Явно указываем дженерик-типы для словаря пулов
        self._pools: Dict[str, AsyncConnectionPool[AsyncConnection[TupleRow]]] = {}
        
        # Общие базовые параметры подключения (без dbname)
        self.host = settings.pg_host
        self.port = settings.pg_port
        self.user = settings.pg_user
        self.password = settings.pg_password

    def _get_conn_info(self, db_name: str) -> str:
        """Формирует строку подключения для конкретной БД"""
        return f"host={self.host} port={self.port} dbname={db_name} user={self.user} password={self.password}"

    async def get_pool(self, db_name: str) -> AsyncConnectionPool:
        """Возвращает существующий пул для БД или создает новый, если его нет"""
        if db_name not in self._pools:
            conn_info = self._get_conn_info(db_name)
            
            logger.info("🧬 Создаю новый пул подключений для базы данных: '%s' ", db_name)
            pool: AsyncConnectionPool[AsyncConnection[TupleRow]] = AsyncConnectionPool(
                conninfo=conn_info,
                min_size=2,
                max_size=10,
                open=False
            )
            # Открываем пул асинхронно
            await pool.open()
            self._pools[db_name] = pool
            
        return self._pools[db_name]

    async def close_all_pools(self):
        """Закрывает все пулы при остановке приложения (FastAPI Lifespan)"""
        logger.info("🛑 Закрытие всех пулов подключений...")
        for db_name, pool in self._pools.items():
            logger.info("Закрываю пул для '%s'...", db_name)
            await pool.close()
        self._pools.clear()

# Создаем один глобальный экземпляр менеджера
pool_manager = DynamicPoolManager()
