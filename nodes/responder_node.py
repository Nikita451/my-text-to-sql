import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import END
from pydantic import SecretStr
from state import AgentState
from config.common_config import settings
from langgraph.types import Command

logger = logging.getLogger(__name__)

RESPONDER_SYSTEM_PROMPT = """Вы — вежливый ИИ-ассистент, аналитик данных.
Ваша задача — взять сухие технические данные из базы данных и перевести их в красивый, структурированный ответ на русском языке для пользователя.

Округляйте денежные суммы до двух знаков после запятой. Если данных нет, так и скажите.
"""

base_llm = ChatOpenRouter(
    model=settings.model,
    api_key=SecretStr(settings.openrouter_api_key),
    temperature=0.5
)

response_llm = base_llm.with_retry(
    stop_after_attempt=3,
    retry_if_exception_type=(Exception, ValueError),
    wait_exponential_jitter=True # делает паузы между попытками чуть-чуть случайными
)


async def responder_node(state: AgentState) -> Command:
    logger.info("✍️ [АГЕНТ-КОПИРАЙТЕР]: Стилизую ответ для пользователя...")
    
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
    
    response = await response_llm.ainvoke(formatted_prompt)

    if response is None:
        raise ValueError("ИИ-модель вернула пустой ответ. Требуется повторная попытка.")
    
    # В самом конце мы возвращаем ответ в messages, чтобы пользователь его увидел,
    # и ОБЯЗАТЕЛЬНО очищаем sql_result, чтобы на следующем вопросе Роутер не запутался!
    return Command(
        goto=END,
        update={
            "messages": [response],
            "sql_result": None # Сбрасываем данных для следующего вопроса!
        }
    )
