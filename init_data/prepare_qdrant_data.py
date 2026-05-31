from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, SparseVector, VectorParams, SparseVectorParams, PointStruct, NamedVector, NamedSparseVector
from fastembed import TextEmbedding, SparseTextEmbedding

client = QdrantClient(url="http://localhost:6333")
COLLECTION_NAME = "db_metadata"

dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

def create_hybrid_collection() -> None:
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

def upload_schema_data() -> None:
    """Генерирует векторы и загружает данные через upsert."""
    documents: List[Dict[str, Any]] = [
        {
            "text": "Таблица users (пользователи). Содержит: id (INT, PK), email (VARCHAR), created_at (TIMESTAMP). Используется для поиска информации о регистрации клиентов.",
            "metadata": {"table_name": "users", "type": "schema"}
        },
        {
            "text": "Таблица orders (заказы). Содержит: id (INT), user_id (FK к users.id), amount (DECIMAL - сумма заказа), status (VARCHAR). Статусы: 'completed' (завершен), 'pending' (ожидает оплаты), 'canceled' (отменен).",
            "metadata": {"table_name": "orders", "type": "schema"}
        },
        {
            "text": "Пример SQL для расчета выручки по клиентам: SELECT u.email, SUM(o.amount) FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = 'completed' GROUP BY u.email;",
            "metadata": {"table_name": "orders", "type": "example_query"}
        }
    ]
    
    texts: List[str] = [doc["text"] for doc in documents]
    
    # Генерируем плотные и разреженные векторы вручную через FastEmbed
    print("Генерация векторов...")
    dense_vectors = list(dense_model.embed(texts))
    sparse_vectors = list(sparse_model.embed(texts))
    
    points: List[PointStruct] = []
    
    for i, doc in enumerate(documents):
        # Превращаем разреженный вектор FastEmbed в формат Qdrant
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
            id=i + 1,
            vector=raw_vectors,
            payload=payload
        )
        points.append(point)
    
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"Успешно загружено {len(points)} точек в Qdrant через upsert.")

if __name__ == "__main__":
    create_hybrid_collection()
    upload_schema_data()

