from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, SparseVector, VectorParams, SparseVectorParams, PointStruct, NamedVector, NamedSparseVector
from fastembed import TextEmbedding, SparseTextEmbedding
import os
import psycopg
from dotenv import load_dotenv
from psycopg import sql

load_dotenv()
db_name = "vasya"

client = QdrantClient(url="http://localhost:6333")
COLLECTION_DB_NAME = "vasya"

dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")



def create_hybrid_collection(COLLECTION_NAME: str) -> None:
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
        print(f"Старая коллекция '{COLLECTION_NAME}' успешно удалена.")
        
    client.create_collection(
        collection_name=COLLECTION_NAME,
        # плотный вектор "dense"
        vectors_config={
            # COSINE является безопасным выбором для легкой модели. 
            "dense": VectorParams(size=384, distance=Distance.COSINE)
        },
        # разреженный вектор
        sparse_vectors_config={
            "sparse": SparseVectorParams()
        }
    )
    print(f"Коллекция '{COLLECTION_NAME}' создана с именами 'dense' и 'sparse'.")


def get_schemas_from_postgres(db_name: str) -> List[Dict[str, Any]]:
    """Автоматически вытаскивает структуру таблиц, колонок и комментарии из Postgres"""
    print("Извлечение метаданных из Postgres...")
    
    POSTGRES_CONN_STR = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={db_name} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    # Этот SQL-запрос собирает имя таблицы, её комментарий, а также список колонок с типами
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
    with psycopg.connect(POSTGRES_CONN_STR) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            
            for row in rows:
                table_name, table_comment, columns = row
                comment_str = f" Описание: {table_comment}." if table_comment else ""
                
                # Формируем текст для векторного поиска
                text = f"Таблица {table_name}.{comment_str} Содержит поля: {columns}."
                
                documents.append({
                    "text": text,
                    "metadata": {"table_name": table_name, "type": "schema"}
                })
    return documents


def get_few_shot_examples() -> List[Dict[str, Any]]:
    """Словарь 'золотых' банковских запросов (Few-Shot) для обучения LLM"""
    examples = [
        {
            "text": "Вопрос: Найди клиентов со статусом VIP и их общий баланс по всем расчетным счетам. "
                    "SQL: SELECT c.customer_id, c.first_name, c.last_name, SUM(a.balance) AS total_balance "
                    "FROM customers c JOIN accounts a ON c.customer_id = a.customer_id "
                    "WHERE c.status = 'vip' AND a.account_type = 'checking' GROUP BY c.customer_id, c.first_name, c.last_name;",
            "metadata": {"table_name": "customers,accounts", "type": "example_query"}
        },
        {
            "text": "Вопрос: Какая сумма трат была в категории Супермаркеты по картам платежной системы Мир за всё время? "
                    "SQL: SELECT SUM(t.amount) AS total_spent FROM transactions t "
                    "JOIN accounts a ON t.account_id = a.account_id "
                    "JOIN cards c ON a.account_id = c.account_id "
                    "WHERE t.category = 'Супермаркеты' AND c.payment_system = 'Мир' AND t.transaction_type = 'payment';",
            "metadata": {"table_name": "transactions,cards,accounts", "type": "example_query"}
        },
        {
            "text": "Вопрос: Выведи топ-3 филиала по количеству открытых счетов. "
                    "SQL: SELECT b.branch_name, COUNT(a.account_id) AS accounts_count FROM branches b "
                    "JOIN accounts a ON b.branch_id = a.branch_id "
                    "GROUP BY b.branch_id, b.branch_name ORDER BY accounts_count DESC LIMIT 3;",
            "metadata": {"table_name": "branches,accounts", "type": "example_query"}
        },
        {
            "text": "Вопрос: Покажи клиентов, у которых есть просроченные кредиты (статус overdue), и сумму их долга. "
                    "SQL: SELECT c.first_name, c.last_name, l.remaining_amount FROM customers c "
                    "JOIN loans l ON c.customer_id = l.customer_id WHERE l.status = 'overdue';",
            "metadata": {"table_name": "customers,loans", "type": "example_query"}
        }
    ]
    return examples



def main(db_col_name: str):
    # 0 Создаем коллекцию
    create_hybrid_collection(db_col_name)

    # 1. Собираем документы (Схемы из БД + Написанные Few-Shot примеры)
    schema_docs = get_schemas_from_postgres(db_col_name)
    example_docs = get_few_shot_examples()
    all_documents = schema_docs + example_docs

    texts: List[str] = [doc["text"] for doc in all_documents]
    
    # 2. Генерируем векторы
    print(f"Генерация векторов для {len(texts)} документов...")
    dense_vectors = list(dense_model.embed(texts))
    sparse_vectors = list(sparse_model.embed(texts))
    
    points: List[PointStruct] = []
    
    for i, doc in enumerate(all_documents):
        sparse_vector_indices = sparse_vectors[i].indices.tolist()
        sparse_vector_values = sparse_vectors[i].values.tolist()

        payload = doc["metadata"]
        payload["document"] = doc["text"]

        raw_vectors = {
            "dense": dense_vectors[i].tolist(),
            "sparse": {
                "indices": sparse_vector_indices,
                "values": sparse_vector_values
            }
        }
        
        point = PointStruct(
            id=i + 1,  # В проде лучше использовать uuid
            vector=raw_vectors,
            payload=payload
        )
        points.append(point)
    
    # 3. Отправляем в Qdrant
    print(f"Загрузка {len(points)} точек в Qdrant коллекцию '{db_col_name}'...")
    
    client.upsert(collection_name=db_col_name, points=points)
    print("Qdrant успешно заполнен!")


if __name__ == "__main__":
    main(COLLECTION_DB_NAME)

