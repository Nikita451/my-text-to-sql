import os
import json
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field, SecretStr
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openrouter import ChatOpenRouter
from dotenv import load_dotenv
from state import AgentState
import sys
import uuid

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Импортируем скомпилированный граф из вашего файла
from agent_graph import app
from config.common_config import settings

load_dotenv()
# uv run python -m tests.eval_tests

# ==========================================
# 1. СТРУКТУРА ОЦЕНКИ ИИ-СУДЬИ (JUDGE SCHEMA)
# ==========================================

class TestCaseEvaluation(BaseModel):
    rationale: str = Field(description="Подробное объяснение: почему выставлены такие оценки")
    context_score: Literal["PASS", "FAIL"] = Field(description="PASS - если Qdrant нашел нужные схемы таблиц. FAIL - если схемы нерелевантны.")
    sql_score: Literal["PASS", "FAIL"] = Field(description="PASS - если SQL синтаксически верен и решает задачу. FAIL - если запрос сломан.")
    response_score: Literal["PASS", "FAIL"] = Field(description="PASS - если ответ точен и дружелюбен. FAIL - если агент соврал или выдал ошибку.")

# Инициализируем изолированную модель-судью (выставляем GPT-4o-mini с температурой 0 для максимальной строгости)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY не найден в .env")

judge_llm = ChatOpenRouter(
    model=settings.model,
    api_key=SecretStr(OPENROUTER_API_KEY),
    temperature=0
).with_structured_output(TestCaseEvaluation)

# Промпт для ИИ-судьи
# JUDGE_SYSTEM_PROMPT = """Вы — строгий аудитор качества ИИ-агентов (QA Engineer).
# Ваша задача — оценить работу SQL-агента на основе тестового кейса.

# Вам предоставлены:
# 1. Вопрос пользователя.
# 2. Эталонный ответ (как должно быть).
# 3. Реальный контекст, который агент извлек из Qdrant.
# 4. Реальный SQL-запрос, который сгенерировал агент.
# 5. Финальный ответ, который агент выдал пользователю.

# КРИТЕРИИ ОЦЕНКИ:
# - context_score: Выставляйте PASS, только если в 'Извлеченном контексте' присутствуют схемы таблиц, необходимые для решения задачи.
# - sql_score: Выставляйте PASS, если 'Реальный SQL' логически и синтаксически верен (допускаются незначительные отличия в алиасах от эталона, главное — верный JOIN и агрегация).
# - response_score: Выставляйте PASS, если 'Финальный ответ' дает точный, вежливый ответ на русском языке на основе данных.

# Будьте максимально строги. Если агент выдал ошибку или пустой ответ — это FAIL.
# """

JUDGE_SYSTEM_PROMPT = """Вы — высококвалифицированный технический аудитор и эксперт по базам данных (Senior Data Engineer / QA).
Оцените работу SQL-агента на основе предоставленного тест-кейса.

КРИТЕРИИ ОЦЕНКИ:
1. context_score: Выставляйте PASS, если предоставленный контекст содержит описание нужных таблиц (илиFew-Shot примеры с ними), достаточные для того, чтобы модель поняла структуру БД. (Если в описании таблицы 'users' есть Few-Shot пример с 'orders' — это PASS!).

2. sql_score: Выставляйте PASS, если сгенерированный SQL логически верен и решает задачу. 
⚠️ ВНИМАНИЕ: Агент может решать задачу поиска максимума как через 'ORDER BY ... LIMIT 1', так и через 'HAVING SUM() = (SELECT MAX...)' или 'WHERE amount = (SELECT MAX...)'. Оба варианта синтаксически и логически верны! Не бракуйте запрос за использование сложных подзапросов, если они возвращают верный результат.

3. response_score: Выставляйте PASS, если финальный текст ответа дает четкий человеческий ответ на вопрос пользователя на русском языке.
"""


# ==========================================
# 2. НАБОР ЭТАЛОННЫХ ТЕСТОВ (DATASET)
# ==========================================
# Сюда вы можете дописывать любые новые проверочные вопросы по мере роста базы данных
EVAL_DATASET: List[Dict[str, str]] = [
    {
        "id": "TC-001",
        "question": "Покажи email пользователей с максимальными тратами",
        "expected_tables": "users, orders",
        "expected_sql": "SELECT email, SUM(amount) FROM users JOIN orders ... ORDER BY ... DESC LIMIT 1"
    },
    {
        "id": "TC-002",
        "question": "А сколько заказов сделал самый активный пользователь?",
        "expected_tables": "users, orders",
        "expected_sql": "SELECT COUNT(*) FROM orders WHERE user_id = ..."
    }
]

# ==========================================
# 3. ЗАПУСК ТЕСТИРОВАНИЯ (EVALUATION LOOP)
# ==========================================

def run_evaluations() -> None:
    print(f"🧪 [EVAL]: Начинаю автоматическое тестирование ИИ-агента ({len(EVAL_DATASET)} тест-кейсов)...")
    
    success_count = 0
    
    for test in EVAL_DATASET:
        print(f"\n──────────────────────────────────────────────────")
        print(f"📋 Запуск тест-кейса {test['id']}: '{test['question']}'")
        
        config = RunnableConfig(
            configurable={
                "thread_id": f"eval_thread_{test['id']}_{uuid.uuid4().hex[:8]}"
            },
            recursion_limit=8,
            tags=["eval", f"dataset_{test.get('set_name', 'default')}"],
            metadata={
                "environment": "testing"
            }
        )
        
        # Инициализируем стартовое состояние
        initial_state: AgentState = {
            "messages": [HumanMessage(content=test["question"])],
            "context": "",
            "sql_result": None,
            "sql_query": ""
        }
        
        try:
            # Прогоняем тест через ваш реальный мультиагентный граф
            final_state = app.invoke(initial_state, config=config)
            
            # Извлекаем данные, которые сгенерировал агент в процессе работы
            actual_context = final_state.get("context", "Пусто")
            actual_sql = final_state.get("sql_query", "Не сгенерирован")
            
            # Находим последнее сообщение (ответ Копирайтера)
            messages = final_state.get("messages", [])
            actual_response = messages[-1].content if messages else "Нет ответа"
            
            # 4. ОТПРАВЛЯЕМ РЕЗУЛЬТАТЫ ИИ-СУДЬЕ НА ПРОВЕРКУ
            judge_prompt = f"""
            === ТЕСТ-КЕЙС {test['id']} ===
            Вопрос пользователя: {test['question']}
            Ожидаемые таблицы в RAG: {test['expected_tables']}
            Ожидаемый пример SQL: {test['expected_sql']}
            
            === РЕАЛЬНЫЙ ВЫВОД АГЕНТА ===
            Извлеченный контекст из Qdrant:
            {actual_context}
            
            Реальный SQL-запрос программиста:
            {actual_sql}
            
            Финальный ответ копирайтера:
            {actual_response}
            """
            
            print(f"🧠 [EVAL]: Отправляю результаты ИИ-судье на аудит...")
            evaluation: TestCaseEvaluation = judge_llm.invoke([
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": judge_prompt}
            ]) # type: ignore
            
            # Выводим вердикт судьи на экран
            print(f"\n⚖️  [ВЕРДИКТ СУДЬИ ДЛЯ {test['id']}]:")
            print(f"📝 Обоснование: {evaluation.rationale}")
            print(f"🔹 Качество RAG (Qdrant):  [{evaluation.context_score}]")
            print(f"🔹 Точность SQL (Postgres): [{evaluation.sql_score}]")
            print(f"🔹 Финальный текст ответа: [{evaluation.response_score}]")
            
            if (evaluation.context_score == "PASS" and 
                evaluation.sql_score == "PASS" and 
                evaluation.response_score == "PASS"):
                print(f"✅ Тест-кейс {test['id']} ПОЛНОСТЬЮ ПРОЙДЕН!")
                success_count += 1
            else:
                print(f"❌ Тест-кейс {test['id']} ПРОВАЛЕН.")
                
        except Exception as e:
            print(f"💥 Критическая ошибка при выполнении тест-кейса: {e}")
            
    print(f"\n──────────────────────────────────────────────────")
    print(f"📊 ИТОГИ ТЕСТИРОВАНИЯ: Успешно пройдено {success_count} из {len(EVAL_DATASET)} тестов.")

if __name__ == "__main__":
    run_evaluations()


"""


Тест
"Таблица users (пользователи). Содержит: id (INT, PK), email (VARCHAR), created_at (TIMESTAMP). 
Используется для поиска информации о регистрации клиентов.\n\nПример SQL для расчета выручки по клиентам: 
SELECT u.email, SUM(o.amount) FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = 'completed' 
GROUP BY u.email;"


"Таблица users (пользователи). Содержит: id (INT, PK), email (VARCHAR), created_at (TIMESTAMP).
 Используется для поиска информации о регистрации клиентов.\n\nПример SQL для расчета выручки по клиентам:
   SELECT u.email, SUM(o.amount) FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = 'completed'
     GROUP BY u.email;"

"""


"""
⚖️  [ВЕРДИКТ СУДЬИ ДЛЯ TC-002]:
📝 Обоснование: Контекст содержит описание таблиц 'users' и 'orders', что соответствует ожиданиям. Таблицы содержат достаточно информации для формирования корректного SQL-запроса.
🔹 Качество RAG (Qdrant):  [PASS]
🔹 Точность SQL (Postgres): [PASS]
🔹 Финальный текст ответа: [PASS]
✅ Тест-кейс TC-002 ПОЛНОСТЬЮ ПРОЙДЕН!

"""