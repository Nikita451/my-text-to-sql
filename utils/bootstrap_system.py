import logging
import psycopg
from psycopg import sql
from config.common_config import settings
from config.db import BASE_CONN_STR
from config.db_manager import pool_manager

logger = logging.getLogger(__name__)


async def bootstrap_system() -> None:
    """Полный цикл инициализации: создает системную БД и накатывает таблицы через пул."""
    
    # --- Шаг 1: Создание физической БД (Строго прямое соединение с autocommit) ---
    logger.info("Шаг 1: Проверка и создание системной базы данных...")
    async with await psycopg.AsyncConnection.connect(
        BASE_CONN_STR, 
        autocommit=True
    ) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s;", 
                (settings.system_db_name,)
            )
            if not await cur.fetchone():
                logger.info("База данных '%s' не найдена. Создаю...", settings.system_db_name)
                await cur.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.system_db_name))
                )
            else:
                logger.info("База данных '%s' уже существует.", settings.system_db_name)

    logger.info("Шаг 2: Инициализация системных таблиц в базе '%s' через пул...", settings.system_db_name)
    system_pool = await pool_manager.get_pool(settings.system_db_name)
    
    # Берем асинхронное соединение ИЗ ПУЛА
    async with system_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id INT NOT NULL,
                    name VARCHAR(150) NOT NULL,
                    description TEXT,
                    internal_db_name VARCHAR(64) NOT NULL UNIQUE,
                    internal_col_name VARCHAR(64) UNIQUE,          
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
    logger.info("Системное окружение PostgreSQL полностью инициализировано и пул готов к работе!")
