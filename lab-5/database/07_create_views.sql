BEGIN;

CREATE VIEW lab5.available_books AS
SELECT
    b.book_id,
    b.isbn,
    b.title,
    a.first_name || ' ' || a.last_name AS author_name,
    c.category_name,
    b.price,
    b.stock_quantity
FROM bookstore.books b
JOIN bookstore.authors a USING (author_id)
JOIN bookstore.categories c USING (category_id)
WHERE b.stock_quantity > 0;

CREATE VIEW lab5.customer_sales AS
SELECT
    c.customer_id,
    c.full_name,
    COUNT(DISTINCT o.order_id) AS confirmed_orders,
    COALESCE(SUM(oi.quantity), 0) AS purchased_copies,
    COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_spent,
    MAX(o.confirmed_at) AS last_purchase_at
FROM bookstore.customers c
LEFT JOIN bookstore.orders o
    ON o.customer_id = c.customer_id
   AND o.status = 'Confirmed'
LEFT JOIN bookstore.order_items oi USING (order_id)
GROUP BY c.customer_id, c.full_name;

COMMIT;
