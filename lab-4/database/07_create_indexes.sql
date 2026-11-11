BEGIN;
CREATE INDEX books_author_idx ON bookstore.books(author_id);
CREATE INDEX books_category_price_idx ON bookstore.books(category_id,price,book_id);
CREATE INDEX orders_customer_created_idx ON bookstore.orders(customer_id,created_at DESC);
CREATE INDEX orders_confirmed_at_idx ON bookstore.orders(confirmed_at) WHERE status='Confirmed';
CREATE INDEX order_items_book_idx ON bookstore.order_items(book_id);
CREATE INDEX activity_log_created_idx ON bookstore.activity_log(created_at DESC);
COMMIT;
