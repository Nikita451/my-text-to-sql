import onnxruntime as ort
from typing import Dict, Any, List, Tuple
from qdrant_client import AsyncQdrantClient
from langgraph.types import Command
from fastembed import SparseTextEmbedding, TextEmbedding
from langchain_core.messages import AIMessage
from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector
from state import AgentState
from config.common_config import settings
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config.db import fastembed_executor, async_qdrant_client

# 1. Создаем настройки для ONNX Runtime
session_options = ort.SessionOptions()

# Ограничиваем количество потоков (Внутренние потоки C++)
session_options.intra_op_num_threads = 2
session_options.inter_op_num_threads = 2

# Отключаем глобальный пул потоков, чтобы сессия использовала только свои личные
session_options.use_per_session_threads = True 

# Инициализируем локальные эмбеддинги
dense_model = TextEmbedding(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    session_options=session_options
)
sparse_model = SparseTextEmbedding(
    model_name="prithivida/Splade_PP_en_v1",
    session_options=session_options
)

async def get_embedding_async(user_text: str) -> list[float]:
    """Асинхронная обертка над FastEmbed с использованием нашего пула."""
    
    # Получаем текущий запущенный Event Loop
    loop = asyncio.get_running_loop()
    
    # Аналог "промисификации" в JS, но с привязкой к конкретному пулу потоков.
    # Шаблон: loop.run_in_executor(пул, функция_без_скобок, аргумент1, аргумент2...)
    dense_embeddings = await loop.run_in_executor(
        fastembed_executor, 
        dense_model.embed, 
        [user_text]
    )
    
    # Превращаем результат генератора в обычный список
    # (так как list() тоже занимает время, его лучше делать прямо здесь)
    return list(dense_embeddings)[0].tolist()

async def generate_rag_vectors(user_text: str) -> Tuple[List[float], list]:
    """
    Одновременно и асинхронно генерирует плотный и разреженный векторы,
    используя единый кастомный пул потоков.
    """
    loop = asyncio.get_running_loop()
    
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

async def qdrant_rag_node(state: AgentState) -> Command:
    """Узел-Библиотекарь: ищет схемы в Qdrant и сохраняет их в контекст графа."""
    print("📚 [АГЕНТ QDRANT]: Начинаю поиск DDL-схем и метаданных в базе знаний...")
    
    if not state.get("messages"):
        # return {"context": state.get("context", "")}
        return Command(goto="router")
        
    # Извлекаем текст последнего вопроса пользователя
    user_text: str = str(state["messages"][-1].content)
    
    # 1. Генерируем плотный и разреженный векторы локально через FastEmbed
    query_dense, query_sparse = await generate_rag_vectors(user_text)
    
    # 2. Выполняем гибридный поиск (Dense + Sparse через RRF) в вашей коллекции db_metadata
    search_result = await async_qdrant_client.query_points(
    
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
