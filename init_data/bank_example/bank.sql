-- ============================================================================
-- 1. Удаление старых таблиц (с учетом зависимостей CASCADE)
-- ============================================================================
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ============================================================================
-- 2. Создание таблиц и метаданных для ИИ
-- ============================================================================

-- Таблица пользователей
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Комментарии для ИИ-агента по таблице users
COMMENT ON TABLE users IS 'Информация о зарегистрированных пользователях (клиентах). Используется для идентификации клиентов и анализа даты их регистрации.';
COMMENT ON COLUMN users.id IS 'Первичный ключ. Уникальный идентификатор пользователя.';
COMMENT ON COLUMN users.email IS 'Электронная почта пользователя. Всегда уникальна. Использовать для вывода контактов клиента.';
COMMENT ON COLUMN users.created_at IS 'Дата и время регистрации пользователя в системе.';


-- Таблица заказов
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL
);

-- Комментарии для ИИ-агента по таблице orders
COMMENT ON TABLE orders IS 'Данные по заказам клиентов. Связана с users. Используется для расчета выручки, среднего чека и анализа статусов заказов.';
COMMENT ON COLUMN orders.id IS 'Первичный ключ. Уникальный идентификатор заказа.';
COMMENT ON COLUMN orders.user_id IS 'Внешний ключ (Foreign Key). Ссылка на users.id. Показывает, какой клиент совершил заказ.';
COMMENT ON COLUMN orders.amount IS 'Сумма заказа в денежном выражении. Использовать SUM(amount) для расчета выручки или доходов.';
COMMENT ON COLUMN orders.status IS 'Статус заказа. Валидные значения: ''completed'' (завершен/оплачен, учитывается в выручке), ''pending'' (ожидает оплаты), ''canceled'' (отменен).';

-- ============================================================================
-- 3. Наполнение тестовыми данными
-- ============================================================================
INSERT INTO users (email) 
VALUES 
    ('alice@example.com'),
    ('bob@example.com'),
    ('charlie@example.com');

INSERT INTO orders (user_id, amount, status) 
VALUES 
    (1, 150.00, 'completed'),
    (1, 300.50, 'completed'),
    (2, 50.00, 'completed'),
    (3, 999.99, 'pending'),
    (3, 120.00, 'completed');
