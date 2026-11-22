BEGIN;

DO $$
BEGIN
    IF current_database() <> 'bookstore_lab5' THEN
        RAISE EXCEPTION 'Скрипт потрібно виконувати в bookstore_lab5';
    END IF;

    IF EXISTS (SELECT 1 FROM bookstore.books WHERE book_id >= 1000000)
       OR EXISTS (SELECT 1 FROM bookstore.customers WHERE customer_id >= 1000000)
       OR EXISTS (SELECT 1 FROM bookstore.orders WHERE order_id >= 1000000) THEN
        RAISE EXCEPTION 'Діапазон демонстраційних ідентифікаторів уже зайнятий';
    END IF;
END;
$$;

CREATE SCHEMA lab5;

CREATE TABLE lab5.dataset_info (
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    generated_books INTEGER NOT NULL,
    generated_customers INTEGER NOT NULL,
    generated_orders INTEGER NOT NULL,
    generated_items INTEGER NOT NULL
);

LOCK TABLE bookstore.books, bookstore.customers, bookstore.orders,
    bookstore.order_items IN SHARE ROW EXCLUSIVE MODE;

-- Масове навчальне наповнення не потребує окремого аудиту кожного з 630 000 рядків.
-- Вимкнення та повернення тригерів є частиною однієї транзакції.
ALTER TABLE bookstore.books DISABLE TRIGGER books_audit;
ALTER TABLE bookstore.customers DISABLE TRIGGER customers_audit;
ALTER TABLE bookstore.orders DISABLE TRIGGER orders_audit;
ALTER TABLE bookstore.order_items DISABLE TRIGGER order_items_audit;

WITH source AS (
    SELECT n, '979' || LPAD(n::TEXT, 9, '0') AS isbn_prefix
    FROM generate_series(1, 20000) AS numbers(n)
), isbn_values AS (
    SELECT
        n,
        isbn_prefix || (
            (10 - (
                SELECT SUM(
                    SUBSTRING(isbn_prefix FROM position FOR 1)::INTEGER
                    * CASE WHEN position % 2 = 1 THEN 1 ELSE 3 END
                ) % 10
                FROM generate_series(1, 12) AS digits(position)
            )) % 10
        )::TEXT AS isbn
    FROM source
)
INSERT INTO bookstore.books (
    book_id, isbn, title, author_id, category_id,
    publication_year, price, stock_quantity
)
SELECT
    1000000 + n,
    isbn,
    'Навчальна книга ' || n,
    1 + (n * 7) % 10,
    1 + n % 10,
    1950 + n % 77,
    100 + ((n * 73) % 90000) / 100.0,
    1000
FROM isbn_values;

INSERT INTO bookstore.customers (customer_id, full_name, email, phone)
SELECT
    1000000 + n,
    'Навчальний покупець ' || n,
    'lab5.customer.' || n || '@example.com',
    '+380' || LPAD(n::TEXT, 9, '0')
FROM generate_series(1, 10000) AS numbers(n);

WITH source AS (
    SELECT
        n,
        CURRENT_TIMESTAMP - ((n * 37) % 730) * INTERVAL '1 day'
            - ((n * 107) % 86400) * INTERVAL '1 second' AS placed_at,
        CASE
            WHEN n % 10 < 7 THEN 'Confirmed'
            WHEN n % 10 < 9 THEN 'Draft'
            ELSE 'Cancelled'
        END AS status
    FROM generate_series(1, 200000) AS numbers(n)
)
INSERT INTO bookstore.orders (order_id, customer_id, status, created_at, confirmed_at)
SELECT
    1000000 + n,
    1000001 + (n * 13) % 10000,
    status,
    placed_at,
    CASE WHEN status = 'Confirmed' THEN placed_at + INTERVAL '10 minutes' END
FROM source;

INSERT INTO bookstore.order_items (order_id, book_id, quantity, unit_price)
SELECT
    1000000 + n,
    b.book_id,
    1 + (n + position) % 3,
    b.price
FROM generate_series(1, 200000) AS numbers(n)
CROSS JOIN generate_series(0, 1) AS positions(position)
JOIN bookstore.books b
    ON b.book_id = 1000001 + (n * 17 + position * 199) % 20000;

-- Залишки враховують лише підтверджені продажі з навчального набору.
WITH sold AS (
    SELECT oi.book_id, SUM(oi.quantity) AS quantity
    FROM bookstore.order_items oi
    JOIN bookstore.orders o USING (order_id)
    WHERE o.order_id > 1000000 AND o.status = 'Confirmed'
    GROUP BY oi.book_id
)
UPDATE bookstore.books b
SET stock_quantity = b.stock_quantity - sold.quantity
FROM sold
WHERE b.book_id = sold.book_id;

ALTER TABLE bookstore.books ENABLE TRIGGER books_audit;
ALTER TABLE bookstore.customers ENABLE TRIGGER customers_audit;
ALTER TABLE bookstore.orders ENABLE TRIGGER orders_audit;
ALTER TABLE bookstore.order_items ENABLE TRIGGER order_items_audit;

SELECT setval(pg_get_serial_sequence('bookstore.books', 'book_id'), MAX(book_id))
FROM bookstore.books;
SELECT setval(pg_get_serial_sequence('bookstore.customers', 'customer_id'), MAX(customer_id))
FROM bookstore.customers;
SELECT setval(pg_get_serial_sequence('bookstore.orders', 'order_id'), MAX(order_id))
FROM bookstore.orders;

-- Прибираємо три індекси з lab-4 лише в копії БД, щоб виміряти початковий план.
DROP INDEX IF EXISTS bookstore.books_category_price_idx;
DROP INDEX IF EXISTS bookstore.orders_customer_created_idx;
DROP INDEX IF EXISTS bookstore.orders_confirmed_at_idx;

INSERT INTO lab5.dataset_info (
    generated_books, generated_customers, generated_orders, generated_items
)
VALUES (20000, 10000, 200000, 400000);

COMMIT;

ANALYZE bookstore.books;
ANALYZE bookstore.customers;
ANALYZE bookstore.orders;
ANALYZE bookstore.order_items;

SELECT * FROM lab5.dataset_info;
