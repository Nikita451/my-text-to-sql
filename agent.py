import os
from typing import TypedDict, List, Dict, Any, Optional, cast, LiteralString

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
import psycopg
from psycopg import sql

from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector
from fastembed import TextEmbedding, SparseTextEmbedding

from langchain_openai import ChatOpenAI
from langchain_openrouter import ChatOpenRouter
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

from langgraph.checkpoint.memory import MemorySaver 
from pydantic import SecretStr
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. НАСТРОЙКА СТРУКТУР И МОДЕЛЕЙ
# ==========================================

class Message(TypedDict):
    role: str
    content: str

class AgentState(TypedDict):
    messages: List[Message] # Память будет здесь, накапливая историю
    context: str
    sql_query: str
    sql_result: Optional[str]
    error: Optional[str]
    final_response: Optional[str]

class GeneratedSQL(BaseModel):
    reasoning: str = Field(description="Логика рассуждения")
    sql_query: str = Field(description="Чистый SQL-запрос")

dense_model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY не найден в .env")

# основная модель для генерации SQL (со Structured Outputs)
llm = ChatOpenRouter(
    model="openai/gpt-4o-mini", 
    api_key=SecretStr(OPENROUTER_API_KEY),
    temperature=0
)
structured_llm = llm.with_structured_output(GeneratedSQL)

response_llm = ChatOpenRouter(
    model="openai/gpt-4o-mini",
    api_key=SecretStr(OPENROUTER_API_KEY),
    temperature=0.5
)

CONN_STR = f"host={os.getenv('PG_HOST', 'localhost')} port={os.getenv('PG_PORT', '5432')} dbname={os.getenv('PG_DB', 'mydb')} user={os.getenv('PG_USER', 'myuser')} password={os.getenv('PG_PASSWORD', 'mypassword')}"

SQL_AGENT_PROMPT = """Вы — эксперт по SQL. Переведите вопрос пользователя в SQL-запрос для PostgreSQL.
Используйте ТОЛЬКО таблицы из предоставленного КОНТЕКСТА:
===
{context}
===

{error_instruction}

Правила:
1. Не придумывайте таблицы.
2. Пишите только чистый SQL, без markdown-разметки (```sql).
"""

# ПРОМПТ: для финального ответа
HUMAN_RESPONSE_PROMPT = """Вы — дружелюбный ИИ-ассистент аналитик данных.
Сформулируйте красивый, понятный человеку ответ на русском языке на основе последнего технического ответа из БД.

1. ИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА (для контекста):
===
{history}
===

2. ТЕКУЩИЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ (на который нужно ответить сейчас):
"{user_question}"

3. ТЕХНИЧЕСКИЙ ОТВЕТ ИЗ БАЗЫ ДАННЫХ (PostgreSQL):
===
{sql_result}
===

Дай четкий ответ на последний вопрос. Округляй суммы до двух знаков.
"""

# ==========================================
# 2. ОПРЕДЕЛЕНИЕ УЗЛОВ ГРАФА (NODES)
# ==========================================

def retrieve_from_qdrant_node(state: AgentState) -> Dict[str, Any]:
    if not state.get("messages"):
        return {"context": ""}
    # Всегда берем самое последнее сообщение пользователя для поиска схем
    user_text: str = state["messages"][-1].get("content", "")
    
    # Генерируем векторы для поискового запроса локально
    query_dense = list(dense_model.embed([user_text]))[0].tolist()
    query_sparse = list(sparse_model.embed([user_text]))
    
    # Выполняем гибридный поиск (Dense + Sparse через RRF)
    search_result = qdrant_client.query_points(
        collection_name="db_metadata",
        prefetch=[
            # 1. Поиск по смыслу (Плотный вектор)
            Prefetch(query=query_dense, using="dense", limit=3),
            # 2. Поиск по ключевым словам (Разреженный вектор)
            Prefetch(
                query=SparseVector(
                    indices=query_sparse[0].indices.tolist(),
                    values=query_sparse[0].values.tolist()
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


def agent_sql_generation_node(state: AgentState) -> Dict[str, Any]:
    """Узел Агента: пишет или ИСПРАВЛЯЕТ SQL-запрос."""
    db_context: str = state.get("context", "")
    user_question: str = state["messages"][-1].get("content", "") if state.get("messages") else ""
    
    # Если на прошлом шаге была ошибка, формируем инструкцию по исправлению
    last_error = state.get("error")
    if last_error:
        error_instruction = f"⚠️ ВНИМАНИЕ: Твой предыдущий SQL-запрос '{state.get('sql_query')}' упал с ошибкой:\n'{last_error}'\nИсправь её!"
    else:
        error_instruction = ""

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SQL_AGENT_PROMPT),
        ("human", "Вопрос: {question}")
    ])
    
    formatted_prompt = prompt_template.format_messages(
        context=db_context,
        question=user_question,
        error_instruction=error_instruction
    )
    
    response: GeneratedSQL = structured_llm.invoke(formatted_prompt) # type: ignore
    return {"sql_query": response.sql_query, "error": None}


def execute_sql_node(state: AgentState) -> Dict[str, Any]:
    """Узел ВЫПОЛНЕНИЯ: запускает запрос в Postgres и ловит ошибки."""
    query_str = state.get("sql_query", "")
    if not query_str or "ERROR" in query_str:
        return {"sql_result": None, "error": "Запрос не сгенерирован"}

    try:
        with psycopg.connect(CONN_STR) as conn:
            with conn.cursor() as cur:
                safe_query = cast(LiteralString, query_str)
                cur.execute(safe_query)
                colnames = [desc.name for desc in cur.description] if cur.description else []
                rows = cur.fetchall() if cur.description else []
                
                result_str = f"Колонки: {colnames}\nСтроки:\n" + "\n".join([str(row) for row in rows])
                print(f"✅ Успешное выполнение SQL!")
                return {"sql_result": result_str, "error": None}
                
    except Exception as e:
        print(f"❌ Ошибка в SQL запросе: {e}")
        return {"sql_result": None, "error": str(e)}


def respond_to_user_node(state: AgentState) -> Dict[str, Any]:
    """Узел СИНТЕЗА ОТВЕТА: генерирует текст и сохраняет его В ИСТОРИЮ сообщений."""
    raw_result = state.get("sql_result")
    sql_result_data: str = raw_result if raw_result is not None else "Нет данных"
    
    current_user_question: str = state["messages"][-1].get("content", "") if state.get("messages") else ""
    # Форматируем историю прошлых сообщений для промпта
    history_str = ""
    if state.get("messages"):
        for msg in state["messages"][:-1]: 
            history_str += f"{msg['role']}: {msg['content']}\n"

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", HUMAN_RESPONSE_PROMPT)
    ])
    
    formatted_prompt = prompt_template.format_messages(
        history=history_str if history_str else "История пуста",
        sql_result=sql_result_data,
        user_question=current_user_question
    )
    
    response = response_llm.invoke(formatted_prompt)
    response_text = str(response.content)
    
    # ГЛАВНОЕ ДЛЯ ПАМЯТИ: Дописываем ответ бота в текущий список сообщений,
    # чтобы при следующем шаге модель видела, что она ответила ранее.
    updated_messages = list(state["messages"])
    updated_messages.append({"role": "assistant", "content": response_text})
    
    return {"final_response": response_text, "messages": updated_messages}

# ==========================================
# 3. СБОРКА ГРАФА С КЛЮЧОМ ПАМЯТИ (CHECKPOINTER)
# ==========================================

memory = MemorySaver()

workflow = StateGraph(AgentState)
workflow.add_node("metadata_retriever", retrieve_from_qdrant_node)
workflow.add_node("sql_generator", agent_sql_generation_node)
workflow.add_node("sql_executor", execute_sql_node)
workflow.add_node("human_responder", respond_to_user_node)

workflow.add_edge(START, "metadata_retriever")
workflow.add_edge("metadata_retriever", "sql_generator")
workflow.add_edge("sql_generator", "sql_executor")

def should_continue(state: AgentState) -> str:
    if state.get("error") is not None:
        print("🔄 *Цикл исправления ошибок* ...")
        return "sql_generator"
    return "human_responder"

workflow.add_conditional_edges("sql_executor", should_continue)
workflow.add_edge("human_responder", END)

app = workflow.compile(checkpointer=memory)

# ==========================================
# 4. ИМИТАЦИЯ ДИАЛОГА (ЧАТ-РЕЖИМ)
# ==========================================
if __name__ == "__main__":
    # Задаем конфигурацию потока. Любые запросы с thread_id="1" будут иметь общую память!
    # config = {"configurable": {"thread_id": "1"}}
    config: RunnableConfig = {"configurable": {"thread_id": "1"}}
    
    # --- ШАГ 1: Первый сложный вопрос ---
    print("--- ВОПРОС 1 ---")
    state_1: AgentState = {
        "messages": [{"role": "user", "content": "Покажи email пользователей, которые потратили больше всего денег"}],
        "context": "", "sql_query": "", "sql_result": None, "error": None, "final_response": None
    }
    final_state_1 = app.invoke(state_1, config=config) # Передаем config с thread_id
    print(f"Бот: {final_state_1.get('final_response')}\n")
    
    # --- ШАГ 2: Уточняющий вопрос (Контекстный!) ---
    print("--- ВОПРОС 2 (Уточняющий) ---")
    state_2: AgentState = {
        "messages": [{"role": "user", "content": "А сколько всего заказов сделал первый пользователь из этого списка?"}],
        "context": "", "sql_query": "", "sql_result": None, "error": None, "final_response": None
    }
    final_state_2 = app.invoke(state_2, config=config) # Передаем ТОТ ЖЕ config
    print(f"Бот: {final_state_2.get('final_response')}\n")
