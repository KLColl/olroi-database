BEGIN;

CREATE INDEX lab5_orders_customer_created_idx
ON bookstore.orders (customer_id, created_at DESC, order_id DESC)
INCLUDE (status);

CREATE INDEX lab5_orders_confirmed_date_idx
ON bookstore.orders (confirmed_at, order_id)
WHERE status = 'Confirmed';

CREATE INDEX lab5_books_available_category_price_idx
ON bookstore.books (category_id, price, book_id)
WHERE stock_quantity > 0;

COMMIT;

ANALYZE bookstore.orders;
ANALYZE bookstore.books;
