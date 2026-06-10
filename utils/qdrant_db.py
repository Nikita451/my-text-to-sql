import logging
from typing import Any, Dict, List, Tuple

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams, SparseVectorParams
import asyncio

from core.fastembed_executor import get_fastembed_executor
from core.vector_models import get_dense_model, get_sparse_model

logger = logging.getLogger(__name__)
dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")


async def create_hybrid_collection(async_qdrant_client: AsyncQdrantClient, col_name: str) -> None:
    exists_col = await async_qdrant_client.collection_exists(col_name)

    if exists_col:
        await async_qdrant_client.delete_collection(col_name)
        logger.info("Старая коллекция '%s' успешно удалена.", col_name)
        
    await async_qdrant_client.create_collection(
        collection_name=col_name,
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
    logger.info("Коллекция '%s' успешно создана с конфигурацией (Dense + Sparse).", col_name)



async def create_document_in_qdrant(
        async_qdrant_client: AsyncQdrantClient, 
        col_name: str, 
        all_documents: List[Dict[str, Any]]):
    texts: List[str] = [doc["text"] for doc in all_documents]
    
    # 2. Генерируем векторы
    logger.info("Генерация векторов для '%s' документов...", len(texts))
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
    logger.info("Загрузка '%s' точек в Qdrant коллекцию '%s'...", len(points), col_name)
    
    await async_qdrant_client.upsert(collection_name=col_name, points=points)
    logger.info("Qdrant успешно заполнен!")
    


async def generate_rag_vectors(user_text: str) -> Tuple[List[float], list]:
    """
    Одновременно и асинхронно генерирует плотный и разреженный векторы,
    используя единый кастомный пул потоков.
    """
    loop = asyncio.get_running_loop()

    dense_model = get_dense_model()
    sparse_model = get_sparse_model()
    fastembed_executor = get_fastembed_executor()
    
    # 1. Запускаем обе тяжелые задачи в пул потоков параллельно
    dense_task = loop.run_in_executor(
        fastembed_executor, 
        lambda: list(dense_model.embed([user_text]))[0].tolist()
    )
    
    sparse_task = loop.run_in_executor(
        fastembed_executor, 
        lambda: list(sparse_model.embed([user_text]))
    )
    
    # 2. Ждем выполнения обеих задач
    query_dense, query_sparse = await asyncio.gather(dense_task, sparse_task)
    
    return query_dense, query_sparse