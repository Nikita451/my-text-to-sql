import hashlib
import logging
import time
from typing import Any, Dict, List, LiteralString, cast

import psycopg
from config.db import BASE_CONN_STR
from psycopg import AsyncConnection, sql
from config.db_manager import pool_manager
import os
from psycopg import Connection
from config.common_config import settings

from core.exceptions import DatabaseAlreadyExistsError, WorkspaceNotFoundError

logger = logging.getLogger(__name__)

def generate_secure_db_name(user_id: int, project_title: str) -> str:
    """Генерирует гарантированно уникальное и безопасное имя для Postgres"""
    # Создаем уникальную строку (соль)
    raw_string = f"user_{user_id}_{project_title}_{time.time()}"
    
    # Хэшируем через md5 (для имен БД длины md5 в 32 символа хватает с запасом)
    db_hash = hashlib.md5(raw_string.encode('utf-8')).hexdigest()
    
    # Имя БД в Postgres должно начинаться с буквы, поэтому добавляем префикс
    return f"tenant_{user_id}_{db_hash}"


async def create_database(db_name: str):
    # 2. Создаем саму базу данных в Postgres
    # PG не позволяет создать БД в рамках пула подключения к другой БД. 
    async with await psycopg.AsyncConnection.connect(BASE_CONN_STR, autocommit=True) as conn:
        async with conn.cursor() as cur:
            # Проверяем существование
            await cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
            if await cur.fetchone():
                raise DatabaseAlreadyExistsError(db_name)
                # raise HTTPException(status_code=400, detail=f"База данных '{db_name}' уже существует.")
            
            # Создаем базу
            await cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))


async def execute_script(db_name: str, sql_content: str):
    # Накатываем SQL-скрипт
    # Получаем пул для новой БД (он создастся автоматически благодаря нашему менеджеру)
    pool = await pool_manager.get_pool(db_name)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # @todo написать валидацию sql
            validated_literal = cast(LiteralString, sql_content)
            safe_sql = sql.SQL(validated_literal)
            await cur.execute(safe_sql)


async def fetch_postgres_schemas(conn: AsyncConnection) -> List[Dict[str, Any]]:
    """Собирает структуру таблиц, используя предоставленное соединение."""
    logger.info("Начало извлечения метаданных из базы данных...")
    
    query = """
    SELECT 
        t.table_name,
        obj_description(pgc.oid, 'pg_class') AS table_comment,
        string_agg(c.column_name || ' (' || c.data_type || ')', ', ' ORDER BY c.ordinal_position) AS columns
    FROM information_schema.tables t
    JOIN pg_catalog.pg_class pgc ON t.table_name = pgc.relname
    JOIN information_schema.columns c ON t.table_name = c.table_name
    WHERE t.table_schema = 'public' 
      AND t.table_type = 'BASE TABLE'
    GROUP BY t.table_name, pgc.oid;
    """
    
    documents = []
    async with conn.cursor() as cur:
        await cur.execute(query)
        rows = await cur.fetchall()
        
        for row in rows:
            table_name, table_comment, columns = row
            comment_str = f" Описание: {table_comment}." if table_comment else ""
            text = f"Таблица {table_name}.{comment_str} Содержит поля: {columns}."
            
            documents.append({
                "text": text,
                "metadata": {"table_name": table_name, "type": "schema"}
            })
            
    logger.info("Успешно извлечено таблиц: %d", len(documents))
    return documents


async def register_workspace_in_system(
    user_id: int, 
    name: str, 
    description: str | None, 
    internal_db_name: str
) -> None:
    """Записывает данные о созданном воркспейсе в системную таблицу 'workspaces'."""
    logger.info("Регистрация нового воркспейса '%s' в системной БД...", internal_db_name)
    
    system_pool = await pool_manager.get_pool(settings.system_db_name)
    
    query = """
    INSERT INTO workspaces (user_id, name, description, internal_db_name, internal_col_name)
    VALUES (%s, %s, %s, %s, %s);
    """
    
    # Берем соединение из пула системной БД
    async with system_pool.connection() as conn:
        async with conn.cursor() as cur:
            # Безопасно передаем параметры через кортеж
            await cur.execute(
                query, 
                (user_id, name, description, internal_db_name, internal_db_name)
            )
            
    logger.info("Воркспейс '%s' успешно зарегистрирован.", internal_db_name)


async def fetch_user_workspaces(user_id: int) -> List[Dict[str, Any]]:
    """Возвращает список всех зарегистрированных воркспейсов для конкретного пользователя."""
    # Получаем пул к системной базе
    system_pool = await pool_manager.get_pool(settings.system_db_name)
    
    query = """
    SELECT id, name, description, internal_db_name, internal_col_name, created_at
    FROM workspaces
    WHERE user_id = %s
    ORDER BY created_at DESC;
    """
    
    workspaces = []
    async with system_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (user_id,))
            rows = await cur.fetchall()
            
            for row in rows:
                workspaces.append({
                    "id": str(row[0]), # Превращаем объект UUID в строку
                    "name": row[1],
                    "description": row[2],
                    "internal_db_name": row[3],
                    "internal_col_name": row[4],
                    "created_at": row[5]
                })
                
    return workspaces


async def fetch_workspace_by_id(workspace_id: str) -> Dict[str, Any]:
    """Возвращает метаданные одного воркспейса по его UUID."""
    # Получаем пул к системной базе
    system_pool = await pool_manager.get_pool(settings.system_db_name)
    
    query = """
    SELECT id, name, description, internal_db_name, internal_col_name, created_at
    FROM workspaces
    WHERE id = %s;
    """
    
    async with system_pool.connection() as conn:
        async with conn.cursor() as cur:
            # Безопасно передаем UUID
            await cur.execute(query, (workspace_id,))
            row = await cur.fetchone()
            
            if not row:
                raise WorkspaceNotFoundError(workspace_id)
                
            return {
                "id": str(row[0]),
                "name": row[1],
                "description": row[2],
                "internal_db_name": row[3],
                "internal_col_name": row[4],
                "created_at": row[5]
            }