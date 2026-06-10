import logging
from typing import List
from core.qdrant_client import get_qdrant_client
from langgraph.types import Command
from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector
from state import AgentState
from utils.qdrant_db import generate_rag_vectors

logger = logging.getLogger(__name__)

async def qdrant_rag_node(state: AgentState) -> Command:
    """Узел-Библиотекарь: ищет схемы в Qdrant и сохраняет их в контекст графа."""
    logger.info("📚 [АГЕНТ QDRANT]: Начинаю поиск DDL-схем и метаданных в базе знаний...")
    
    if not state.get("messages"):
        return Command(goto="router")
        
    # Извлекаем текст последнего вопроса пользователя
    user_text: str = str(state["messages"][-1].content)
    col_name: str = state['col_name']
    
    # 1. Генерируем плотный и разреженный векторы локально через FastEmbed
    query_dense, query_sparse = await generate_rag_vectors(user_text)

    async_qdrant_client = get_qdrant_client()
    
    # 2. Выполняем гибридный поиск (Dense + Sparse через RRF) в вашей коллекции
    search_result = await async_qdrant_client.query_points(
        collection_name=col_name,
        prefetch=[
            Prefetch(query=query_dense, using="dense", limit=5),
            Prefetch(
                query=SparseVector(
                    indices=query_sparse[0].indices.tolist(),
                    values=query_sparse[0].values.tolist()
                ),
                using="sparse", 
                limit=5
            )
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=5,
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
        
    logger.info("✅ [АГЕНТ QDRANT]: Контекст успешно обновлен. Найдено документов: %s", len(fetched_texts))
    
    return Command(
        goto="router",
        update={
            "context": combined_context
        }
    )
