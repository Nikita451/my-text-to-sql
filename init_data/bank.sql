-- ============================================================================
-- 1. ОЧИСТКА СТАРЫХ ТАБЛИЦ (Порядок важен из-за Foreign Keys)
-- ============================================================================
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS cards CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS loans CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS branches CASCADE;

-- ============================================================================
-- 2. СОЗДАНИЕ ТАБЛИЦ И КОММЕНТАРИЕВ ДЛЯ LLM
-- ============================================================================

-- Филиалы банка
CREATE TABLE branches (
    branch_id SERIAL PRIMARY KEY,
    branch_name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    address VARCHAR(255) NOT NULL
);
COMMENT ON TABLE branches IS 'Справочник филиалов и отделений банка';

-- Клиенты банка
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'blocked', 'vip')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE customers IS 'Информация о клиентах банка, их статусах и контактных данных';

-- Счета клиентов
CREATE TABLE accounts (
    account_id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id) ON DELETE CASCADE,
    branch_id INT REFERENCES branches(branch_id),
    account_number VARCHAR(20) UNIQUE NOT NULL,
    account_type VARCHAR(20) CHECK (account_type IN ('checking', 'savings', 'deposit')),
    balance NUMERIC(15, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'RUB',
    is_active BOOLEAN DEFAULT TRUE,
    opened_at DATE DEFAULT CURRENT_DATE
);
COMMENT ON TABLE accounts IS 'Банковские счета клиентов (расчетные, сберегательные, вклады) и их текущие балансы';

-- Банковские карты
CREATE TABLE cards (
    card_id SERIAL PRIMARY KEY,
    account_id INT REFERENCES accounts(account_id) ON DELETE CASCADE,
    card_number VARCHAR(16) UNIQUE NOT NULL,
    card_holder VARCHAR(100) NOT NULL,
    payment_system VARCHAR(20) CHECK (payment_system IN ('Мир', 'Visa', 'Mastercard')),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'expired', 'blocked')),
    expiry_date DATE NOT NULL
);
COMMENT ON TABLE cards IS 'Пластиковые и виртуальные карты, привязанные к счетам клиентов';

-- Транзакции (Операции по счетам)
CREATE TABLE transactions (
    transaction_id SERIAL PRIMARY KEY,
    account_id INT REFERENCES accounts(account_id) ON DELETE CASCADE,
    amount NUMERIC(15, 2) NOT NULL,
    transaction_type VARCHAR(20) CHECK (transaction_type IN ('deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'payment')),
    category VARCHAR(50) CHECK (category IN ('Супермаркеты', 'Кафе и рестораны', 'Транспорт', 'Переводы', 'Пополнение', 'Коммунальные услуги')),
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- COMMENT ON TABLE transactions IS 'История всех денежных операций (транзакций) по счетам: списания, пополнения, категории трат';
COMMENT ON TABLE transactions IS 'История всех денежных операций. Расходы и списания (transaction_type = ''payment'', ''withdrawal'', ''transfer_out'') записываются со знаком МИНУС. При расчете сумм трат и расходов всегда инвертируйте знак или используйте функцию ABS(), чтобы финальная сумма для пользователя была положительной.';

-- Кредиты
CREATE TABLE loans (
    loan_id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id) ON DELETE CASCADE,
    loan_amount NUMERIC(15, 2) NOT NULL,
    interest_rate NUMERIC(4, 2) NOT NULL, -- Процентная ставка, например 14.50
    term_months INT NOT NULL,
    remaining_amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paid', 'overdue')),
    issued_at DATE DEFAULT CURRENT_DATE
);
COMMENT ON TABLE loans IS 'Информация о выданных кредитах, процентных ставках, сроках и остатке задолженности';


-- ============================================================================
-- 3. НАПОЛНЕНИЕ ДАННЫМИ (SEED DATA)
-- ============================================================================

INSERT INTO branches (branch_name, city, address) VALUES
('Центральный', 'Москва', 'ул. Тверская, д. 12'),
('Невский', 'Санкт-Петербург', 'Невский пр., д. 45'),
('Сибирский', 'Новосибирск', 'ул. Ленина, д. 5');

INSERT INTO customers (first_name, last_name, email, phone, status) VALUES
('Иван', 'Иванов', 'ivanov@email.com', '+79991112233', 'vip'),
('Анна', 'Смирнова', 'smirnovaa@email.com', '+79992223344', 'active'),
('Петр', 'Петров', 'petrov@email.com', '+79993334455', 'active'),
('Елена', 'Сидорова', 'sidorovae@email.com', '+79994445566', 'blocked');

INSERT INTO accounts (customer_id, branch_id, account_number, account_type, balance, currency) VALUES
(1, 1, '40817810000000000001', 'checking', 150000.00, 'RUB'),
(1, 1, '40817810000000000002', 'savings', 500000.00, 'RUB'),
(2, 2, '40817810000000000003', 'checking', 45000.50, 'RUB'),
(3, 3, '40817810000000000004', 'checking', 12000.00, 'RUB'),
(4, 1, '40817810000000000005', 'deposit', 1000000.00, 'RUB');

INSERT INTO cards (account_id, card_number, card_holder, payment_system, status, expiry_date) VALUES
(1, '2200111122223333', 'IVAN IVANOV', 'Мир', 'active', '2028-12-31'),
(3, '4111222233334444', 'ANNA SMIRNOVA', 'Visa', 'active', '2027-05-31'),
(4, '5555666677778888', 'PETR PETROV', 'Mastercard', 'blocked', '2025-01-01');

INSERT INTO transactions (account_id, amount, transaction_type, category, description) VALUES
(1, -1500.00, 'payment', 'Супермаркеты', 'Покупка в Пятерочке'),
(1, -450.00, 'payment', 'Кафе и рестораны', 'Кофе в Шоколаднице'),
(2, 5000.00, 'deposit', 'Пополнение', 'Проценты по вкладу'),
(3, -200.00, 'payment', 'Транспорт', 'Оплата метро Яндекс Go'),
(3, 40000.00, 'transfer_in', 'Переводы', 'Зарплата'),
(4, -3000.00, 'withdrawal', 'Коммунальные услуги', 'Оплата ЖКХ');

INSERT INTO loans (customer_id, loan_amount, interest_rate, term_months, remaining_amount, status) VALUES
(1, 500000.00, 12.50, 36, 350000.00, 'active'),
(2, 100000.00, 15.00, 12, 0.00, 'paid'),
(3, 300000.00, 14.00, 24, 310000.00, 'overdue'); -- Опережает график или штрафы
