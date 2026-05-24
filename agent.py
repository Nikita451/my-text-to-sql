from typing import TypedDict, List, Dict, Any
from pydantic import BaseModel, Field, SecretStr
from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, QueryRequest, FusionQuery, Fusion, SparseVector
from fastembed import TextEmbedding, SparseTextEmbedding
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
import os

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

class Message(TypedDict):
    role: str
    content: str

class AgentState(TypedDict):
    messages: List[Message]
    context: str
    sql_query: str

class GeneratedSQL(BaseModel):
    reasoning: str = Field(description="Логика рассуждения: почему выбраны эти таблицы")
    sql_query: str = Field(description="Чистый SQL-запрос")

# Инициализируем локальные эмбеддинги (те же, что и при индексации)
dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

if not OPENROUTER_API_KEY:
    raise ValueError("Ошибка: Переменная OPENROUTER_API_KEY не найдена в файле .env")

qdrant_client = QdrantClient(url=QDRANT_URL)
llm = ChatOpenAI(
    model="openai/gpt-4o-mini",
    api_key=SecretStr(OPENROUTER_API_KEY),
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
    default_headers={
        "HTTP-Referer": "https://localhost:3000",
        "X-Title": "My SQL RAG Agent",
    }
)

structured_llm = llm.with_structured_output(GeneratedSQL)

SQL_AGENT_PROMPT = """Вы — эксперт по SQL. Переведите вопрос пользователя в SQL-запрос.
Используйте ТОЛЬКО таблицы из предоставленного КОНТЕКСТА:
===
{context}
===
Правила:
1. Не придумывайте таблицы.
2. Пишите только чистый SQL, без markdown-разметки (```sql).
"""

def retrieve_from_qdrant_node(state: AgentState) -> Dict[str, str]:
    """Узел RAG: делает гибридный поиск по структуре базы данных."""
    if not state.get("messages"):
        return {"context": ""}
        
    user_text: str = state["messages"][-1].get("content", "")
    
    # Генерируем векторы для поискового запроса локально
    query_dense = list(dense_model.embed([user_text]))[0].tolist()
    query_sparse = list(sparse_model.embed([user_text]))[0]
    
    # Выполняем гибридный поиск (Dense + Sparse через RRF)
    search_result = qdrant_client.query_points(
        collection_name="db_metadata",
        prefetch=[
            # 1. Поиск по смыслу (Плотный вектор)
            Prefetch(query=query_dense, using="dense", limit=3),
            
            # 2. Поиск по ключевым словам (Разреженный вектор)
            Prefetch(
                query=SparseVector(
                    indices=query_sparse.indices.tolist(),
                    values=query_sparse.values.tolist()
                ), 
                using="sparse", 
                limit=3
            )
        ],
        # гибридный поиск ! Алгоритм RRF
        query=FusionQuery(fusion=Fusion.RRF),
        limit=2,
        with_payload=True
    )
    
    # Собираем найденные описания таблиц в единый текст
    fetched_texts: List[str] = []
    if search_result.points:
        for point in search_result.points:
            if point.payload and "document" in point.payload:
                fetched_texts.append(str(point.payload["document"]))
                
    return {"context": "\n\n".join(fetched_texts)}


def agent_sql_generation_node(state: AgentState) -> Dict[str, str]:
    """Узел Агента: читает схемы таблиц и пишет SQL-запрос."""
    db_context: str = state.get("context", "")
    user_question: str = state["messages"][-1].get("content", "") if state.get("messages") else ""
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SQL_AGENT_PROMPT),
        ("human", "Вопрос: {question}")
    ])
    
    formatted_prompt = prompt_template.format_messages(
        context=db_context,
        question=user_question
    )
    
    response: GeneratedSQL = structured_llm.invoke(formatted_prompt) # type: ignore
    return {"sql_query": response.sql_query}


# Строим линейный граф: Сначала ищем контекст в Qdrant -> потом отдаем в LLM
workflow = StateGraph(AgentState)
workflow.add_node("metadata_retriever", retrieve_from_qdrant_node)
workflow.add_node("sql_generator", agent_sql_generation_node)

workflow.add_edge(START, "metadata_retriever")
workflow.add_edge("metadata_retriever", "sql_generator")
workflow.add_edge("sql_generator", END)

app = workflow.compile()

if __name__ == "__main__":
    test_state: AgentState = {
        "messages": [{"role": "user", "content": "Покажи email пользователей, которые потратили больше всего денег"}],
        "context": "",
        "sql_query": ""
    }
    
    print("Запуск графа...")
    final_state = app.invoke(test_state)
    
    print("\n[НАЙДЕННЫЙ КОНТЕКСТ ИЗ QDRANT]:")
    print(final_state.get("context"))
    
    print("\n[СФОРМИРОВАННЫЙ SQL ЗАПРОС]:")
    print(final_state.get("sql_query"))
