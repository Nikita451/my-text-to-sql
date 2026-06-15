import os
import psycopg
from config.db import BASE_CONN_STR
from dotenv import load_dotenv
from psycopg import sql

load_dotenv()
db_name = "bank_vasya"

def create_database_if_not_exists(TARGET_DB_NAME: str):
    print(f"Проверка существования базы данных '{TARGET_DB_NAME}'...")
    
    with psycopg.connect(BASE_CONN_STR) as conn:
        conn.autocommit = True  
        
        with conn.cursor() as cur:
            # Проверяем, есть ли уже база с таким именем
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s;", 
                (TARGET_DB_NAME,)
            )
            exists = cur.fetchone()
            
            if not exists:
                print(f"База данных '{TARGET_DB_NAME}' не найдена. Создаю...")
                
                query = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TARGET_DB_NAME))
                cur.execute(query)
                
                print(f"База данных '{TARGET_DB_NAME}' успешно создана!")
            else:
                print(f"База данных '{TARGET_DB_NAME}' уже существует.")


def init_db(db_name: str, script_relative_path: str) -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file_path = os.path.join(script_dir, script_relative_path)
    # Подключаемся к PostgreSQL
    conn_str = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={db_name} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    with open(sql_file_path, "r", encoding="utf-8") as f:
        sql_script = f.read()


    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            print('Выполнение скрипта...')
            cur.execute(sql.SQL(sql_script)) # type: ignore
            
            conn.commit()
            print("База данных PostgreSQL успешно инициализирована!")

if __name__ == "__main__":
    """
    Загружаем данные для выполнения тестов
    """
    create_database_if_not_exists("bank_vasya")
    init_db("bank_vasya", "../bank_example/bank.sql")

    create_database_if_not_exists("test_vasya")
    init_db("test_vasya", "../simple_example/simple.sql")
    