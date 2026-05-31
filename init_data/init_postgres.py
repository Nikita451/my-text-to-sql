import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def init_db() -> None:
    # Подключаемся к PostgreSQL
    conn_str = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DB')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            print("Удаление старых таблиц...")
            cur.execute("DROP TABLE IF EXISTS orders CASCADE;")
            cur.execute("DROP TABLE IF EXISTS users CASCADE;")
            
            print("Создание таблиц users и orders...")
            cur.execute("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            cur.execute("""
                CREATE TABLE orders (
                    id SERIAL PRIMARY KEY,
                    user_id INT REFERENCES users(id) ON DELETE CASCADE,
                    amount DECIMAL(10, 2) NOT NULL,
                    status VARCHAR(50) NOT NULL
                );
            """)
            
            print("Наполнение тестовыми данными...")
            # Добавляем пользователей
            users = [
                ("alice@example.com",),
                ("bob@example.com",),
                ("charlie@example.com",)
            ]
            cur.executemany("INSERT INTO users (email) VALUES (%s);", users)
            
            # Добавляем заказы (id юзеров: 1 - Alice, 2 - Bob, 3 - Charlie)
            orders = [
                (1, 150.00, "completed"),
                (1, 300.50, "completed"),  # Alice потратила 450.50
                (2, 50.00, "completed"),   # Bob потратил 50.00
                (3, 999.99, "pending"),    # У Charlie заказ ожидает оплаты (status='pending')
                (3, 120.00, "completed")   # Charlie потратил 120.00
            ]
            cur.executemany("INSERT INTO orders (user_id, amount, status) VALUES (%s, %s, %s);", orders)
            
            conn.commit()
            print("База данных PostgreSQL успешно инициализирована!")

if __name__ == "__main__":
    init_db()
