
# Промпт для копирайтера (он больше не видит технические схемы таблиц, только результат!)
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import END
from pydantic import SecretStr
from state import AgentState
from config.common_config import settings
from langgraph.types import Command

RESPONDER_SYSTEM_PROMPT = """Вы — вежливый ИИ-ассистент, аналитик данных.
Ваша задача — взять сухие технические данные из базы данных и перевести их в красивый, структурированный ответ на русском языке для пользователя.

Округляйте денежные суммы до двух знаков после запятой. Если данных нет, так и скажите.
"""

response_llm = ChatOpenRouter(
    model=settings.model,
    api_key=SecretStr(settings.openrouter_api_key),
    temperature=0.5
)

def responder_node(state: AgentState) -> Command:
    print("✍️ [АГЕНТ-КОПИРАЙТЕР]: Стилизую ответ для пользователя...")
    
    # 1. Извлекаем данные из Postgres
    raw_result = state.get("sql_result")
    sql_result_data = raw_result if raw_result is not None else "Нет данных"
    
    # 2. Передаем их Копирайтеру через ChatPromptTemplate
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", RESPONDER_SYSTEM_PROMPT),
        ("human", "Вопрос: {user_question}\nСырые данные из БД:\n{sql_result}")
    ])
    
    # Достаем оригинальный вопрос человека
    user_question = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            user_question = str(msg.content)
            break
            
    formatted_prompt = prompt_template.format_messages(
        user_question=user_question,
        sql_result=sql_result_data
    )
    
    response = response_llm.invoke(formatted_prompt)
    
    # В самом конце мы возвращаем ответ в messages, чтобы пользователь его увидел,
    # и ОБЯЗАТЕЛЬНО очищаем sql_result, чтобы на следующем вопросе Роутер не запутался!
    return Command(
        goto=END,
        update={
            "messages": [response],
            "sql_result": None # Сбрасываем данных для следующего вопроса!
        }
    )
