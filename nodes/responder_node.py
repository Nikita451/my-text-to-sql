import logging
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import END
from pydantic import BaseModel, Field, SecretStr
from state import AgentState
from config.common_config import settings
from langgraph.types import Command

logger = logging.getLogger(__name__)

# RESPONDER_SYSTEM_PROMPT = """Вы — вежливый ИИ-ассистент, аналитик данных.
# Ваша задача — взять сухие технические данные из базы данных и перевести их в красивый, структурированный ответ на русском языке для пользователя.

# Округляйте денежные суммы до двух знаков после запятой. Если данных нет, так и скажите.
# """

RESPONDER_SYSTEM_PROMPT = """Вы — вежливый ИИ-ассистент, аналитик данных.
Ваша задача — взять сухие технические данные из базы данных и перевести их в красивый, структурированный ответ на русском языке для пользователя.
Твоя задача состоит из ДВУХ НЕЗАВИСИМЫХ шагов:

ШАГ 1: Сформируй подробный текстовый ответ (поле text_answer) на основе данных из `sql_result`. 
Если в `sql_result` есть строки (даже одна), ты ОБЯЗАН перечислить эти данные в тексте. Наличие строк означает, что данные ЕСТЬ.
Если данных нет, прямо скажите об этом пользовател.
ПРАВИЛА ТЕКСТОВОГО ОТВЕТА:
1. Округляйте денежные суммы до двух знаков после запятой. 
2. Если данных нет, прямо скажите об этом пользователю в `text_answer`.
3. Пишите живым, аналитическим языком. Сделайте краткие выводы по полученным данным.

ШАГ 2: Реши, нужен ли график (поле chart). 
Для обычного текстового списка людей график не нужен — в этом случае установи chart = null. 
Внимание: установка chart = null НЕ означает, что данных нет. Это означает лишь отсутствие диаграммы.
ПРАВИЛА ЗАПОЛНЕНИЯ ГРАФИКА (поле chart):
1. Заполняйте объект `chart` ТОЛЬКО в том случае, если в данных есть списки, рейтинги, топы, сравнения или временные ряды, которые целесообразно визуализировать (например: "топ-3 депозита", "динамика баланса за месяц").
2. Выбирайте правильный тип графика (`type`):
   - 'bar' — для сравнения категорий (топы, рейтинги, сравнение вкладов).
   - 'line' — для трендов и изменения данных во времени (даты, месяцы).
   - 'pie' — для отображения долей от целого (структура портфеля).
3. В поле `chart.label` пишите емкое и понятное название графика на русском языке.
4. В массиве `data`:
   - `name` должен содержать короткое текстовое название (например, название депозита или дату). Не делайте имена слишком длинными, чтобы они не ломали фронтенд.
   - `value` должен содержать исключительно число (float или int) без знаков валют, процентов и других символов.
"""
class DataPoint(BaseModel):
    name: str = Field(description="Наименование элемента (ось X). Например, название депозита 'Премиум'")
    value: float = Field(description="Численное значение (ось Y). Например, сумма или процентная ставка")

class ChartData(BaseModel):
    label: str = Field(description="Название графика, например 'Топ 3 депозита по объему'")
    type: str = Field(description="Тип графика для отрисовки: 'bar', 'line', или 'pie'")
    data: List[DataPoint] = Field(description="Массив данных для графика")

class FinalResponse(BaseModel):
    text_answer: str = Field(description="Развернутый текстовый ответ пользователю с анализом данных")
    chart: Optional[ChartData] = Field(
        default=None, 
        description="Заполняй ТОЛЬКО если нужна диаграмма (топы, сравнения, график). Если это просто список людей, пиши сюда null."
    )

base_llm = ChatOpenRouter(
    model=settings.model,
    api_key=SecretStr(settings.openrouter_api_key),
    temperature=0.5
).with_structured_output(FinalResponse)

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
    
    response: FinalResponse = await response_llm.ainvoke(formatted_prompt) # type: ignore

    if response is None:
        raise ValueError("ИИ-модель вернула пустой ответ. Требуется повторная попытка.")
    
    # Формируем сообщение для истории, прикрепляя к нему данные графика
    ai_message = AIMessage(
        content=response.text_answer,
        # Передаем словарь в специальное поле, чтобы LangChain хранил его в истории сообщений
        additional_kwargs={"chart_data": response.chart} if response.chart else {}
    )

    # В самом конце мы возвращаем ответ в messages, чтобы пользователь его увидел,
    # и ОБЯЗАТЕЛЬНО очищаем sql_result, чтобы на следующем вопросе Роутер не запутался!
    return Command(
        goto=END,
        update={
            "messages": [ai_message],
            "chart": response.chart.model_dump() if response.chart else None,
            "sql_result": None # Сбрасываем данных для следующего вопроса!
        }
    )
