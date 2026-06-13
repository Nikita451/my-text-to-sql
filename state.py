
from typing import Annotated, List, Optional, TypedDict

from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]  # Строгая история сообщений LangChain
    context: str                                          # Накопленный контекст из Qdrant
    sql_result: Optional[str]
    sql_query: str
    col_name: str
    db_name: str
    # <- Храним как dict для легкой сериализации (в том числе самим LangGraph при checkpoint-ах)
    chart: Optional[dict]  
