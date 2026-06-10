

import logging

from fastapi import UploadFile
import json
from config.db_manager import pool_manager
import time
import hashlib

from core.exceptions import OnboardingFailedError
from core.qdrant_client import get_qdrant_client
from utils.pg_db import create_database, execute_script, fetch_postgres_schemas, register_workspace_in_system
from utils.qdrant_db import create_document_in_qdrant, create_hybrid_collection

logger = logging.getLogger(__name__)


async def create_workspace(
  name: str,
  description: str,
  sql_file: UploadFile,
  few_shot_file: UploadFile
):
  # 1. Валидация имени БД (безопасность от инъекций в имя базы)
  # @todo заменить 1 реальным идентификатором пользователя после авторизации. 
  user_id = 1
  db_name = generate_secure_db_name(user_id, name)

  try:
      logger.info("1. Создаем базу данных для пользователя: %s", db_name)
      await create_database(db_name)

      logger.info("2. Накатываем пользовательский скрипт...")
      sql_content = (await sql_file.read()).decode("utf-8")
      await execute_script(db_name=db_name, sql_content=sql_content)

      logger.info("3. Загружаем few-shot примеры...")
      few_shot_content = await few_shot_file.read()
      few_shot_examples = json.loads(few_shot_content) # Ожидаем массив [{"text": "...", "metadata": {}}]

      logger.info("4. Загружаем документы в Qdrant...")
      await index_database_metadata_to_qdrant(db_name, few_shot_examples)


      logger.info("5. Создаем новый workspace...")
      await register_workspace_in_system(
            user_id=user_id,
            name=name,
            description=description,
            internal_db_name=db_name
        )

      return {"status": "success", "message": "Workspace успешно создан!"}

  except Exception as e:
      logger.error("Ошибка онбординга БД: %s", str(e), exc_info=True)
      raise OnboardingFailedError(reason=str(e))

def generate_secure_db_name(user_id: int, project_title: str) -> str:
    """Генерирует гарантированно уникальное и безопасное имя для Postgres"""
    # Создаем уникальную строку (соль)
    raw_string = f"user_{user_id}_{project_title}_{time.time()}"
    
    # Хэшируем через md5 (для имен БД длины md5 в 32 символа хватает с запасом)
    db_hash = hashlib.md5(raw_string.encode('utf-8')).hexdigest()
    
    # Имя БД в Postgres должно начинаться с буквы, поэтому добавляем префикс
    return f"tenant_{user_id}_{db_hash}"
  

async def index_database_metadata_to_qdrant(db_name: str, few_shot_examples: list):
    async_qdrant_client = get_qdrant_client()

    logger.info("4.1. Создаем новую коллекцию в Qdrant")
    await create_hybrid_collection(async_qdrant_client, db_name)

    logger.info("4.2. Создаем векторные документы на основе DDL схемы")
    db_pool = await pool_manager.get_pool(db_name)
    schema_docs = []
    async with db_pool.connection() as conn:
        schema_docs = await fetch_postgres_schemas(conn)

    logger.info("4.3. Объединяем документы по схемы и few-shot и загружаем в Qdrant")
    all_documents = schema_docs + few_shot_examples
    await create_document_in_qdrant(async_qdrant_client, db_name, all_documents)

  