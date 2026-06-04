import os
from typing import List
from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector
from fastembed import TextEmbedding, SparseTextEmbedding
from langchain_core.tools import tool

# Инициализируем локальные эмбеддинги
dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

@tool
def get_db_schema_tool(search_query: str) -> str:
    """Поиск в векторной базе знаний Qdrant. Возвращает DDL-схемы таблиц, описание колонок и примеры SQL-запросов по ключевым словам или смыслу."""
    query_dense = list(dense_model.embed([search_query]))[0].tolist()
    query_sparse = list(sparse_model.embed([search_query]))
    
    search_result = qdrant_client.query_points(
        collection_name="db_metadata",
        prefetch=[
            Prefetch(query=query_dense, using="dense", limit=3),
            Prefetch(
                query=SparseVector(
                    indices=query_sparse[0].indices.tolist(),
                    values=query_sparse[0].values.tolist()
                ), 
                using="sparse", 
                limit=3
            )
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=3,
        with_payload=True
    )
    
    fetched_texts: List[str] = []
    if search_result.points:
        for point in search_result.points:
            if point.payload and "document" in point.payload:
                fetched_texts.append(str(point.payload["document"]))
                
    return "\n\n".join(fetched_texts) if fetched_texts else "Схемы не найдены."
