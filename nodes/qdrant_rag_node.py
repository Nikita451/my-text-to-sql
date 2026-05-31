from typing import Dict, Any, List
from langgraph.types import Command
from fastembed import SparseTextEmbedding, TextEmbedding
from langchain_core.messages import AIMessage
from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector
from state import AgentState
from config.common_config import settings

qdrant_client = QdrantClient(url=settings.qdrant_url)
# Инициализируем локальные эмбеддинги
dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

def qdrant_rag_node(state: AgentState) -> Command:
    """Узел-Библиотекарь: ищет схемы в Qdrant и сохраняет их в контекст графа."""
    print("📚 [АГЕНТ QDRANT]: Начинаю поиск DDL-схем и метаданных в базе знаний...")
    
    if not state.get("messages"):
        # return {"context": state.get("context", "")}
        return Command(goto="router")
        
    # Извлекаем текст последнего вопроса пользователя
    user_text: str = str(state["messages"][-1].content)
    
    # 1. Генерируем плотный и разреженный векторы локально через FastEmbed
    query_dense = list(dense_model.embed([user_text]))[0].tolist()
    query_sparse = list(sparse_model.embed([user_text]))
    
    # 2. Выполняем гибридный поиск (Dense + Sparse через RRF) в вашей коллекции db_metadata
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
        limit=2,
        with_payload=True
    )
    
    # 3. Собираем найденные текстовые описания таблиц
    fetched_texts: List[str] = []
    if search_result.points:
        for point in search_result.points:
            if point.payload and "document" in point.payload:
                fetched_texts.append(str(point.payload["document"]))
                
    new_context = "\n\n".join(fetched_texts)
    
    # Склеиваем старый контекст и новый (чтобы не потерять ранее найденные схемы)
    current_context = state.get("context", "")
    if current_context and new_context:
        combined_context = current_context + "\n\n" + new_context
    else:
        combined_context = new_context if new_context else current_context
        
    print(f"✅ [АГЕНТ QDRANT]: Контекст успешно обновлен. Найдено документов: {len(fetched_texts)}")
    
    return Command(
        goto="router",
        update={
            "context": combined_context
        }
    )
