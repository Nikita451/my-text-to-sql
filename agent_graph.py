from langgraph.graph import END, START, StateGraph

from nodes.qdrant_rag_node import qdrant_rag_node
from nodes.router import router_node
from nodes.sql_coder_node import sql_coder_node
from nodes.responder_node import responder_node
from state import AgentState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import RetryPolicy

workflow = StateGraph(AgentState)
memory = MemorySaver()

router_retry_policy = RetryPolicy(
    # Перезапускать при ошибках сети или ошибках парсинга JSON от LangChain
    retry_on=Exception, 
    max_attempts=3,      # Пытаться максимум 3 раза
    backoff_factor=2.0   # Увеличивать время ожидания в 2 раза с каждым сбоем
)

workflow.add_node("router", router_node, retry_policy=router_retry_policy)

workflow.add_node("qdrant_rag", qdrant_rag_node)
workflow.add_node("sql_coder", sql_coder_node)
workflow.add_node("general_responder", responder_node)

workflow.add_edge(START, "router")
workflow.add_edge("qdrant_rag", "router")
workflow.add_edge("sql_coder", "router")
workflow.add_edge("general_responder", END)

# Вместо условного ребра паттерн Command
# workflow.add_conditional_edges("router", route_destination)

app = workflow.compile(checkpointer=memory)
