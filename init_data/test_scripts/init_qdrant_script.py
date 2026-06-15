import asyncio
from typing import List, Dict, Any
from qdrant_client import AsyncQdrantClient
import os
from dotenv import load_dotenv
from psycopg import AsyncConnection
import json

from utils.pg_db import fetch_postgres_schemas
from utils.qdrant_db import create_document_in_qdrant, create_hybrid_collection

load_dotenv()

client = AsyncQdrantClient(url="http://localhost:6333")

async def get_schemas_from_postgres(db_name: str) -> List[Dict[str, Any]]:
    """Автоматически вытаскивает структуру таблиц, колонок и комментарии из Postgres"""
    print("Извлечение метаданных из Postgres...")
    
    POSTGRES_CONN_STR = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={db_name} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    documents = []
    async with await AsyncConnection.connect(POSTGRES_CONN_STR) as conn:
        documents = await fetch_postgres_schemas(conn)
    return documents


def get_few_shot_examples(script_relative_path: str) -> List[Dict[str, Any]]:
    """Словарь 'золотых' банковских запросов (Few-Shot) для обучения LLM"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    few_shot_file_path = os.path.join(script_dir, script_relative_path)
    with open(few_shot_file_path, "r", encoding="utf-8") as f:
        few_shot_script = json.load(f)
    return few_shot_script


async def main(db_col_name: str, few_shot_path: str):
    # 0 Создаем коллекцию
    # create_hybrid_collection(db_col_name)
    await create_hybrid_collection(client, db_col_name)

    # 1. Собираем документы (Схемы из БД + Написанные Few-Shot примеры)
    schema_docs = await  get_schemas_from_postgres(db_col_name)
    example_docs = get_few_shot_examples(few_shot_path)
    all_documents = schema_docs + example_docs
    
    # 2. Генерируем векторы
    await create_document_in_qdrant(client, db_col_name, all_documents=all_documents)

    await client.close()
    print("Qdrant успешно заполнен!")

if __name__ == "__main__":
    """
    Загружаем БД с данными для выполнения тестов. 
    """
    asyncio.run(main("bank_vasya", "../bank_example/bank_few_shot.json"))
    asyncio.run(main("test_vasya", "../simple_example/simple.json"))
# HF_TOKEN