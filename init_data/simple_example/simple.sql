-- ============================================================================
-- 1. Удаление старых таблиц (с учетом зависимостей CASCADE)
-- ============================================================================
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ============================================================================
-- 2. Создание таблиц
-- ============================================================================
-- Таблица пользователей
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица заказов (связана с users через FOREIGN KEY)
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL
);

-- ============================================================================
-- 3. Наполнение тестовыми данными
-- ============================================================================
-- Добавляем пользователей (id сгенерируются автоматически: 1, 2, 3)
INSERT INTO users (email) 
VALUES 
    ('alice@example.com'),
    ('bob@example.com'),
    ('charlie@example.com');

-- Добавляем заказы для созданных пользователей
INSERT INTO orders (user_id, amount, status) 
VALUES 
    (1, 150.00, 'completed'),  -- Alice
    (1, 300.50, 'completed'),  -- Alice
    (2, 50.00, 'completed'),   -- Bob
    (3, 999.99, 'pending'),    -- Charlie
    (3, 120.00, 'completed');  -- Charlie
