import os
from typing import cast, LiteralString
import psycopg
from langchain_core.tools import tool

CONN_STR = f"host={os.getenv('PG_HOST', 'localhost')} port={os.getenv('PG_PORT', '5432')} dbname={os.getenv('PG_DB', 'mydb')} user={os.getenv('PG_USER', 'myuser')} password={os.getenv('PG_PASSWORD', 'mypassword')}"

@tool
def execute_sql_query_tool(sql_query: str) -> str:
    """Выполняет предоставленный SQL-запрос в реальной базе данных PostgreSQL и возвращает строки данных или текст ошибки, если в запросе есть баг."""
    try:
        with psycopg.connect(CONN_STR) as conn:
            with conn.cursor() as cur:
                safe_query = cast(LiteralString, sql_query)
                cur.execute(safe_query)
                colnames = [desc.name for desc in cur.description] if cur.description else []
                rows = cur.fetchall() if cur.description else []
                return f"Успешно!\nКолонки: {colnames}\nСтроки:\n" + "\n".join([str(row) for row in rows])
    except Exception as e:
        return f"ОШИБКА ОТ POSTGRESQL: {e}. Пожалуйста, исправьте синтаксис запроса или имена полей."
