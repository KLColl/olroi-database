BEGIN;
CREATE VIEW bookstore.book_catalog AS
SELECT b.book_id,b.isbn,b.title,b.author_id,
       a.first_name||' '||a.last_name AS author_name,a.country,
       b.category_id,c.category_name,b.publication_year,b.price,b.stock_quantity
FROM bookstore.books b JOIN bookstore.authors a ON a.author_id=b.author_id
JOIN bookstore.categories c ON c.category_id=b.category_id;

CREATE VIEW bookstore.order_summary AS
SELECT o.order_id,o.customer_id,c.full_name AS customer_name,c.email AS customer_email,
       o.status,o.created_at,o.confirmed_at,COUNT(oi.book_id) AS distinct_books,
       COALESCE(SUM(oi.quantity),0) AS total_quantity,
       COALESCE(SUM(oi.quantity*oi.unit_price),0) AS order_total
FROM bookstore.orders o JOIN bookstore.customers c ON c.customer_id=o.customer_id
LEFT JOIN bookstore.order_items oi ON oi.order_id=o.order_id
GROUP BY o.order_id,o.customer_id,c.full_name,c.email,o.status,o.created_at,o.confirmed_at;
COMMIT;
