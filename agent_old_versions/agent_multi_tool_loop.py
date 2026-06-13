import os
from typing import Annotated, TypedDict, List, Dict, Any, cast, LiteralString
from state import AgentState
from pydantic import BaseModel, Field

from psycopg import sql

from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector
from fastembed import TextEmbedding, SparseTextEmbedding

from langchain_openrouter import ChatOpenRouter
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from pydantic import SecretStr
from dotenv import load_dotenv
from langgraph.graph.message import add_messages

from tools.pg_tool import execute_sql_query_tool
from tools.qdrant_tool import get_db_schema_tool 
from config.common_config import settings

load_dotenv()

# ==========================================
# 1. НАСТРОЙКА СОСТОЯНИЯ И КЛИЕНТОВ
# ==========================================


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY не найден в .env")


# Собираем список инструментов и связываем их с моделью
tools = [get_db_schema_tool, execute_sql_query_tool]

llm = ChatOpenRouter(
    model=settings.model, 
    api_key=SecretStr(OPENROUTER_API_KEY),
    temperature=0
).bind_tools(tools) # Передаем инструменты в модель на уровне API!

# Системный промпт диспетчера
AGENT_SYSTEM_PROMPT = """Вы — автономный ИИ-аналитик данных со встроенным доступом к инструментам.
Ваша цель — отвечать на вопросы пользователя на русском языке, используя данные из PostgreSQL.

У ВАС ЕСТЬ ДВА ИНСТРУМЕНТА:
1. 'get_db_schema_tool' — ВСЕГДА вызывайте его сначала, чтобы узнать структуру таблиц, если вы не уверены в именах полей или связях.
2. 'execute_sql_query_tool' — Вызывайте его, чтобы получить реальные данные из таблиц.

ПРАВИЛА:
1. Если инструмент выполнения вернул ошибку PostgreSQL, проанализируйте её текст и исправьте SQL-запрос, вызвав инструмент заново. У вас есть право на ошибку и самоисправление.
2. Когда вы получите успешные данные из БД, переведите их в красивый, понятный человеку финальный ответ на русском языке и выведите его пользователю БЕЗ вызова каких-либо инструментов.
"""

# ==========================================
# 3. ОПРЕДЕЛЕНИЕ УЗЛОВ И ЛОГИКИ ГРАФА
# ==========================================

def call_agent_node(state: AgentState) -> Dict[str, Any]:
    """Узел Агента: анализирует историю и принимает решение (вызвать Tool или ответить)."""
    messages = state["messages"]
    
    # Добавляем системный промпт в начало, если это старт потока
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + messages
        
    response = llm.invoke(messages)
    # Возвращаем новую реплику агента, LangGraph сам допишет её в State благодаря редуктору
    return {"messages": [response]}


# Создаем узел автоматического выполнения инструментов через готовый ToolNode от LangGraph
tool_node = ToolNode(tools)


def should_continue_router(state: AgentState) -> str:
    """Роутер: проверяет, решила ли модель вызвать инструмент или готова выдать ответ."""
    last_message = state["messages"][-1]
    
    # Если в последнем сообщении модели есть запросы на вызов инструментов — отправляем граф на выполнение инструментов
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        print(f"🔄 Агент решил вызвать инструменты: {[t['name'] for t in last_message.tool_calls]}")
        return "tools"
        
    # Если вызовов инструментов нет — агент сформировал текстовый ответ, завершаем граф
    print("🏁 Агент сформировал финальный человеческий ответ.")
    return END

# ==========================================
# 4. СБОРКА И ЗАПУСК ЦИКЛИЧЕСКОГО ГРАФА
# ==========================================

memory = MemorySaver()

workflow = StateGraph(AgentState)
workflow.add_node("agent", call_agent_node)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")

# После узла инструментов граф ВСЕГДА возвращается обратно в Агента, 
# чтобы модель прочитала результаты выполнения инструментов и подумала, что делать дальше.
workflow.add_edge("tools", "agent")

# Назначаем условный переход после узла Агента
workflow.add_conditional_edges("agent", should_continue_router)

app = workflow.compile(checkpointer=memory)

# ==========================================
# 5. ТЕСТ АГЕНТА В ДИАЛОГЕ
# ==========================================
if __name__ == "__main__":
    config = RunnableConfig(configurable={"thread_id": "agent_loop_thread"})
    
    # --- ШАГ 1: Вопрос по известным таблицам ---
    print("\n--- ВОПРОС 1 ---")
    # input_1 = {"messages": [HumanMessage(content="Покажи email пользователей с максимальными тратами")]}
    input_1: AgentState = {
        "messages": [HumanMessage(content="Покажи email пользователей с максимальными тратами")],
        "context": "",
        "sql_result": "",
        "sql_query": "",
        "db_name": "mydb",
        "col_name": "db_metadata",
        "chart": None,
    }

    for event in app.stream(input_1, config=config, stream_mode="values"):
        pass # Запускаем стриминг для прогона всех внутренних петель графа
        
    final_messages = app.get_state(config).values["messages"]
    print(f"Робот: {final_messages[-1].content}\n")
    
    # --- ШАГ 2: ДОП Вопрос ---
    print("--- ВОПРОС 2 (Уточняющий / Повторный RAG) ---")
    # input_2 = {"messages": [HumanMessage(content="А сколько заказов сделал самый активный пользователь?")]}
    input_2: AgentState = {
        "messages": [HumanMessage(content="А сколько заказов сделал самый активный пользователь?")],
        "context": "",
        "sql_result": "",
        "sql_query": "",
        "db_name": "mydb",
        "col_name": "db_metadata",
        "chart": None,
    }

    for event in app.stream(input_2, config=config, stream_mode="values"):
        pass
        
    final_messages = app.get_state(config).values["messages"]
    print(f"Робот: {final_messages[-1].content}")


"""
--- ВОПРОС 1 ---
🔄 Агент решил вызвать инструменты: ['get_db_schema_tool']
🔄 Агент решил вызвать инструменты: ['execute_sql_query_tool']
🏁 Агент сформировал финальный человеческий ответ.
Робот: Email пользователя с максимальными тратами: **alice@example.com**.

--- ВОПРОС 2 (Уточняющий / Повторный RAG) ---
🔄 Агент решил вызвать инструменты: ['execute_sql_query_tool']
🏁 Агент сформировал финальный человеческий ответ.
Робот: Самый активный пользователь сделал **2 заказа**.
"""
