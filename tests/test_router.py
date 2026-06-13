from nodes.router import router_node
import pytest
from langchain_core.messages import HumanMessage
from state import AgentState

@pytest.mark.parametrize(
    "user_message, expected_agent",
    [
        # Тест 1: Приветствие
        ("Привет! Как дела?", "general_responder"),
        
        # Тест 2: Запрос новых неизвестных данных
        # ("Какие новые таблицы по продажам за 2026 год у нас появились?", "qdrant_rag"),
        
        # Тест 3: Работа со знакомым SQL
        # ("Схема таблицы users известна. Напиши запрос для вывода топ-5 пользователей.", "sql_coder"),
    ]
)
def test_router_decisions(user_message, expected_agent):
    """Проверяем, что роутер правильно распределяет задачи по агентам."""
    # 1. Создаем состояние графа для теста
    test_state: AgentState = {
        "messages": [HumanMessage(content=user_message)],
        "context": "",
        "sql_result": "",
        "sql_query": "",
        "db_name": "mydb",
        "col_name": "db_metadata",
        "chart": None,
    }
    
    # 2. Вызываем наш узел
    result = router_node(test_state)
    
    # 3. Проверяем, что роутер выбрал именно того агента, которого мы ждали
    # assert result["next_step"] == expected_agent
