import os
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field, SecretStr, field_validator
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openrouter import ChatOpenRouter
from dotenv import load_dotenv
from state import AgentState
import sys
import uuid
import asyncio
from asgi_lifespan import LifespanManager
from agent import app_fastapi

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Импортируем скомпилированный граф из вашего файла
from agent_graph import app
from config.common_config import settings
from langfuse.callback import CallbackHandler
from pydantic import ValidationError

load_dotenv()

langfuse_callback = CallbackHandler()

"""
ВАЖНО: перед запуском тестов необходимо запустить окружение и 
прогнать скрипты для загрузки тестовых данных.
/init_data/test_scripts/init_pg_script.py - загрузка структурированных данных в PG SQL
/init_data/test_scripts/init_pg_script.py - загрузка векторов в QDRANT.
"""

# ==========================================
# 1. СТРУКТУРА ОЦЕНКИ ИИ-СУДЬИ (JUDGE SCHEMA)
# ==========================================

class TestCaseEvaluation(BaseModel):
    rationale: str = Field(description="Подробное объяснение: почему выставлены такие оценки")
    context_score: Literal["PASS", "FAIL"] = Field(description="PASS - если Qdrant нашел нужные схемы таблиц. FAIL - если схемы нерелевантны.")
    sql_score: Literal["PASS", "FAIL"] = Field(description="PASS - если SQL синтаксически верен и решает задачу. FAIL - если запрос сломан.")
    response_score: Literal["PASS", "FAIL"] = Field(description="PASS - если ответ точен и дружелюбен. FAIL - если агент соврал или выдал ошибку.")

    @field_validator("context_score", "sql_score", "response_score", mode="before")
    @classmethod
    def clean_scores(cls, value: str) -> str:
        """Автоматически находит PASS или FAIL в тексте, если модель написала лишнее"""
        if not isinstance(value, str):
            return value
        
        upper_val = value.upper()
        if "PASS" in upper_val:
            return "PASS"
        if "FAIL" in upper_val:
            return "FAIL"
            
        return value # Если вообще ничего не нашли, отдаем как есть, пусть падает ассерт

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
EVAL_DATASET: List[Dict[str, str]] = [
    {
        "id": "TC-001",
        "question": "Покажи email пользователей с максимальными тратами",
        "expected_tables": "users, orders",
        "expected_sql": "SELECT email, SUM(amount) FROM users JOIN orders ... ORDER BY ... DESC LIMIT 1",
        "db_col_name": "test_vasya",
    },
    {
        "id": "TC-002",
        "question": "А сколько заказов сделал самый активный пользователь?",
        "expected_tables": "users, orders",
        "expected_sql": "SELECT COUNT(*) FROM orders WHERE user_id = ...",
        "db_col_name": "test_vasya",
    },
    {
        "id": "TC-003",
        "question": "Какие траты пользователя с email alice@example.com?",
        "expected_tables": "users, orders",
        "expected_sql": "SELECT SUM(amount) FROM orders JOIN users ... WHERE email = 'alice@example.com' AND status = 'completed'",
        "db_col_name": "test_vasya",
    },
    {
        "id": "TC-004",
        "question": "Покажи список ID заказов, которые еще не были оплачены и висят в ожидании",
        "expected_tables": "orders",
        "expected_sql": "SELECT id FROM orders WHERE status = 'pending'",
        "db_col_name": "test_vasya",
    },
    {
        "id": "TC-005",
        "question": "Сколько всего денег на счетах типа checking (расчетные) и валюта RUB (рубли) ?",
        "expected_tables": "accounts",
        "expected_sql": "SELECT SUM(balance) FROM accounts WHERE account_type = 'checking' AND currency = 'RUB'",
        "db_col_name": "bank_vasya",
    },
    {
        "id": "TC-006",
        "question": "Какую сумму клиент с id = 1 потратил в категории Супермаркеты?",
        "expected_tables": "accounts, transactions",
        "expected_sql": "SELECT ABS(SUM(amount)) FROM transactions t JOIN accounts a ... WHERE a.customer_id = 5 AND t.category = 'Супермаркеты' AND t.transaction_type IN (...)",
        "db_col_name": "bank_vasya",
    },
    {
        "id": "TC-007",
        "question": "Найди клиентов с любой суммой оставшейся задолженности по кредитам",
        "expected_tables": "customers, loans",
        "expected_sql": "SELECT customer_id, SUM(remaining_amount) FROM loans ... WHERE status = 'active' GROUP BY ... ORDER BY ... DESC LIMIT 3",
        "db_col_name": "bank_vasya",
    },
    
    # Проблема высокой семантической плотности ключевых слов. 
    # Велика вероятность что таблицы customers НЕ попадет в список документов от qdrant.
    # Та как ключевое слово 'клиент' присутствует почти во всех таблицах, few-short-примерах!
    # Можно увеличить число документов/поднять семантическую значимость таблицы customers и тд...
    {
        "id": "TC-008",
        "question": "Сколько всего активных клиентов зарегистрировано в банке?",
        "expected_tables": "customers",
        "expected_sql": "SELECT COUNT(*) FROM customers WHERE status = 'active'",
        "db_col_name": "bank_vasya",
    },
    {
        "id": "TC-009",
        "question": "Выведи номера счетов, которые были открыты в текущем 2026 году",
        "expected_tables": "accounts",
        "expected_sql": "SELECT account_number FROM accounts WHERE opened_at >= '2026-01-01' AND opened_at <= '2026-12-31'",
        "db_col_name": "bank_vasya",
    },
    {
        "id": "TC-010",
        "question": "Какой средний баланс на счетах в валюте RUB?",
        "expected_tables": "accounts",
        "expected_sql": "SELECT AVG(balance) FROM accounts WHERE currency = 'RUB'",
        "db_col_name": "bank_vasya",
    },
]

# ==========================================
# 3. ЗАПУСК ТЕСТИРОВАНИЯ (EVALUATION LOOP)
# ==========================================

async def run_evaluations() -> None:
    print(f"🧪 [EVAL]: Начинаю автоматическое тестирование ИИ-агента ({len(EVAL_DATASET)} тест-кейсов)...")
    
    success_count = 0
    
    for test in EVAL_DATASET:
        print(f"\n──────────────────────────────────────────────────")
        print(f"📋 Запуск тест-кейса {test['id']}: '{test['question']}' db/col-name: '{test['db_col_name']}'")
        thread_id = f"eval_thread_{test['id']}_{uuid.uuid4().hex[:8]}"
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
            },
            callbacks=[langfuse_callback],
            recursion_limit=8,
            tags=["eval", f"dataset_{test.get('set_name', 'default')}"],
            metadata={
                "environment": "testing",
                "langfuse_session_id": thread_id,
                "langfuse_user_id": "test_user",
                "langfuse_trace_name": "test_agent_loop_execution"
            }
        )
        
        # Инициализируем стартовое состояние
        initial_state: AgentState = {
            "messages": [HumanMessage(content=test["question"])],
            "context": "",
            "sql_result": None,
            "sql_query": "",
            "db_name": test['db_col_name'],
            "col_name": test['db_col_name'],
            "chart": None,
        }
        
        try:
            final_state = await app.ainvoke(initial_state, config=config)
            
            actual_context = final_state.get("context", "Пусто")
            actual_sql = final_state.get("sql_query", "Не сгенерирован")
            
            # Находим последнее сообщение (ответ Копирайтера)
            messages = final_state.get("messages", [])
            actual_response = messages[-1].content if messages else "Нет ответа"


            # ============================================================================
            # ЭВАЛ-КЕЙСЫ: ПРОГРАММНЫЕ АССЕРТЫ И ВАЛИДАЦИЯ TOOL-ВЫЗОВА
            # ============================================================================
            
            # 1. Проверяем, что граф в принципе вернул сообщения
            assert messages, f"[{test['id']}] Критическая ошибка: граф вернул пустой список сообщений!"
            
            # 2. Валидация tool-вызова (Проверяем Qdrant / Router):
            # Если тест требует таблицы, они ДОЛЖНЫ быть в извлеченном контексте (Qdrant отработал верно)
            if test["expected_tables"] != "none":
                expected_tables_list = [t.strip() for t in test["expected_tables"].split(",")]
                for table in expected_tables_list:
                    assert table.lower() in actual_context.lower(), (
                        f"[{test['id']}] Ошибка валидации Tool-вызова: "
                        f"Таблица '{table}' не найдена в извлеченном контексте Qdrant!"
                    )
            
            # 3. Базовый программный ассерт на SQL (Проверяем SQL Coder):
            # Если ожидается SQL, проверяем, что агент не выдал пустую строку или стандартную заглушку
            if test["expected_sql"] != "none":
                assert actual_sql != "Не сгенерирован" and len(actual_sql) > 10, (
                    f"[{test['id']}] Программный ассерт провален: "
                    f"SQL-запрос не был сгенерирован или слишком короткий!"
                )
                
                # Дополнительный ассерт на отсутствие явных ошибок синтаксиса в самом тексте ответа
                assert "syntax error" not in actual_response.lower(), (
                    f"[{test['id']}] В финальном ответе обнаружена системная ошибка базы данных!"
                )
            
            else:
                assert actual_sql == "Не сгенерирован" or actual_sql == "", (
                    f"[{test['id']}] Ошибка Роутера: "
                    f"Агент попытался сгенерировать SQL для нецелевого запроса!"
                )
            
            print(f"Финальный ответ: {actual_response}")
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
            
            # Настройки ретраев для судьи
            MAX_JUDGE_RETRIES = 3
            judge_success = False

            for attempt in range(1, MAX_JUDGE_RETRIES + 1):
                try:
                    print(f"🧠 [EVAL]: Отправляю результаты ИИ-судье на аудит...")
                    evaluation: TestCaseEvaluation = judge_llm.invoke([
                        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": judge_prompt}
                    ]) # type: ignore
                    judge_success = True
                    break
                except ValidationError as e:
                    print(f"💥 Судья ошибся в формате JSON на попытке {attempt}: {e}")
                    if attempt == MAX_JUDGE_RETRIES:
                        raise AssertionError(f"Не удалось получить валидный ответ от ИИ-судьи после {MAX_JUDGE_RETRIES} попыток.")
                    
                    judge_prompt += "\n⚠️ ВАЖНО: Твой предыдущий ответ вызвал ошибку парсинга! Ответь СТРОГО в формате JSON. Поля context_score, sql_score и response_score должны содержать ТОЛЬКО 'PASS' или 'FAIL'."

            
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

async def run_tests_with_lifecycle():
    print("🚀 [TESTS]: Инициализация окружения (вызов lifespan FastAPI)...")

    # Контекстный менеджер выполнит всё ДО слова yield в lifespan сервиса.
    async with LifespanManager(app_fastapi):
        print("✅ [TESTS]: Окружение готово. Запуск тест-кейсов...")

        # Запускаем тесты
        await run_evaluations()

        print("📋 [TESTS]: Тестирование завершено.")

    # После выхода из блока async with выполнится всё, что написано ПОСЛЕ yield
    print("🛑 [TESTS]: Все ресурсы тестов успешно очищены.")


if __name__ == "__main__":
    asyncio.run(run_tests_with_lifecycle())


"""
Пример успешного запуска: 
🚀 [TESTS]: Инициализация окружения (вызов lifespan FastAPI)...
16:15:51 [INFO] Инициализация кастомного пула потоков для FastEmbed...
16:15:51 [INFO] Загрузка тяжелых ИИ-моделей в память (Dense + Sparse)...
/Users/macbook/Documents/Work/AGENT/my-text-to-sql/core/vector_models.py:41: UserWarning: The model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 now uses mean pooling instead of CLS embedding. In order to preserve the previous behaviour, consider either pinning fastembed version to 0.5.1 or using `add_custom_model` functionality.
  _state.dense = TextEmbedding(
16:15:52 [INFO] ИИ-модели успешно загружены в контейнер состояния.
16:15:52 [INFO] Инициализация асинхронного клиента Qdrant...
16:15:52 [INFO] Шаг 1: Проверка и создание системной базы данных...
16:15:52 [INFO] База данных 'tts_system_db' уже существует.
16:15:52 [INFO] Шаг 2: Инициализация системных таблиц в базе 'tts_system_db' через пул...
16:15:52 [INFO] 🧬 Создаю новый пул подключений для базы данных: 'tts_system_db' 
16:15:52 [INFO] Системное окружение PostgreSQL полностью инициализировано и пул готов к работе!
✅ [TESTS]: Окружение готово. Запуск тест-кейсов...
🧪 [EVAL]: Начинаю автоматическое тестирование ИИ-агента (2 тест-кейсов)...

──────────────────────────────────────────────────
📋 Запуск тест-кейса TC-001: 'Покажи email пользователей с максимальными тратами'
16:15:56 [WARNING] ⚠️ Роутер сбоил (Empty response from LLM). Включаю каскадную защиту.
16:15:56 [INFO] Резервный путь: [Стейт пуст] ➔ Принудительно идем в qdrant_rag
16:15:56 [INFO] 📚 [АГЕНТ QDRANT]: Начинаю поиск DDL-схем и метаданных в базе знаний...
16:15:56 [INFO] ✅ [АГЕНТ QDRANT]: Контекст успешно обновлен. Найдено документов: 5
16:16:00 [WARNING] ⚠️ Роутер сбоил (Empty response from LLM). Включаю каскадную защиту.
16:16:00 [INFO] Резервный путь: [Схемы таблиц есть] ➔ Принудительно идем в sql_coder
16:16:00 [INFO] 💻 [АГЕНТ-ПРОГРАММИСТ]: Начинаю генерацию и выполнение SQL-запроса...
16:16:00 [INFO] 🧬 Создаю новый пул подключений для базы данных: 'test_vasya' 
16:16:00 [INFO] 🤖 [АГЕНТ-ПРОГРАММИСТ]: Попытка 1 из 4...
16:16:06 [INFO] 📝 [АГЕНТ-ПРОГРАММИСТ]: Сгенерирован SQL: WITH UserSpending AS (SELECT u.email, SUM(o.amount) AS total_spent FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = 'completed' GROUP BY u.email) SELECT email FROM UserSpending WHERE total_spent = (SELECT MAX(total_spent) FROM UserSpending);
16:16:06 [INFO] ✅ [АГЕНТ-ПРОГРАММИСТ]: SQL-запрос успешно выполнен!
16:16:06 [INFO] 🧠 [РОУТЕР (Python)]: Данные из Postgres уже в буфере. Направляю к: general_responder
16:16:06 [INFO] ✍️ [АГЕНТ-КОПИРАЙТЕР]: Стилизую ответ для пользователя...
🧠 [EVAL]: Отправляю результаты ИИ-судье на аудит...

⚖️  [ВЕРДИКТ СУДЬИ ДЛЯ TC-001]:
📝 Обоснование: Контекст содержит подробное описание таблиц users и orders, включая их структуру и пример SQL-запроса, что позволяет агенту понять структуру базы данных.
🔹 Качество RAG (Qdrant):  [PASS]
🔹 Точность SQL (Postgres): [PASS]
🔹 Финальный текст ответа: [PASS]
✅ Тест-кейс TC-001 ПОЛНОСТЬЮ ПРОЙДЕН!

──────────────────────────────────────────────────
📋 Запуск тест-кейса TC-002: 'А сколько заказов сделал самый активный пользователь?'
16:16:19 [WARNING] ⚠️ Роутер сбоил (Empty response from LLM). Включаю каскадную защиту.
16:16:19 [INFO] Резервный путь: [Стейт пуст] ➔ Принудительно идем в qdrant_rag
16:16:19 [INFO] 📚 [АГЕНТ QDRANT]: Начинаю поиск DDL-схем и метаданных в базе знаний...
16:16:19 [INFO] ✅ [АГЕНТ QDRANT]: Контекст успешно обновлен. Найдено документов: 5
16:16:23 [WARNING] ⚠️ Роутер сбоил (Empty response from LLM). Включаю каскадную защиту.
16:16:23 [INFO] Резервный путь: [Схемы таблиц есть] ➔ Принудительно идем в sql_coder
16:16:23 [INFO] 💻 [АГЕНТ-ПРОГРАММИСТ]: Начинаю генерацию и выполнение SQL-запроса...
16:16:23 [INFO] 🤖 [АГЕНТ-ПРОГРАММИСТ]: Попытка 1 из 4...
16:16:27 [INFO] 📝 [АГЕНТ-ПРОГРАММИСТ]: Сгенерирован SQL: SELECT user_id, COUNT(*) as order_count FROM orders GROUP BY user_id ORDER BY order_count DESC LIMIT 1;
16:16:27 [INFO] ✅ [АГЕНТ-ПРОГРАММИСТ]: SQL-запрос успешно выполнен!
16:16:27 [INFO] 🧠 [РОУТЕР (Python)]: Данные из Postgres уже в буфере. Направляю к: general_responder
16:16:27 [INFO] ✍️ [АГЕНТ-КОПИРАЙТЕР]: Стилизую ответ для пользователя...
🧠 [EVAL]: Отправляю результаты ИИ-судье на аудит...

⚖️  [ВЕРДИКТ СУДЬИ ДЛЯ TC-002]:
📝 Обоснование: Контекст содержит описание таблиц users и orders, включая их поля и связи, что достаточно для понимания структуры базы данных.
🔹 Качество RAG (Qdrant):  [PASS]
🔹 Точность SQL (Postgres): [PASS]
🔹 Финальный текст ответа: [PASS]
✅ Тест-кейс TC-002 ПОЛНОСТЬЮ ПРОЙДЕН!

──────────────────────────────────────────────────
📊 ИТОГИ ТЕСТИРОВАНИЯ: Успешно пройдено 2 из 2 тестов.
📋 [TESTS]: Тестирование завершено.
16:16:35 [INFO] ⏳ [LIFESPAN]: Закрываем пулы соединений и фоновых потоков...
16:16:35 [INFO] 🛑 Закрытие всех пулов подключений...
16:16:35 [INFO] Закрываю пул для 'tts_system_db'...
16:16:35 [INFO] Закрываю пул для 'test_vasya'...
16:16:35 [INFO] Закрытие соединений с Qdrant...
16:16:35 [INFO] ✅ [LIFESPAN]: Сессия Qdrant успешно закрыта.
16:16:35 [INFO] Завершение работы пула потоков FastEmbed...
16:16:35 [INFO] 🛑 [LIFESPAN]: Все пулы успешно остановлены. Сервер выключен.
🛑 [TESTS]: Все ресурсы тестов успешно очищены.


+ LangFuse: test_user...
"""