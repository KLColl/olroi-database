SELECT 'books' AS table_name, COUNT(*) AS total_rows,
       COUNT(*) FILTER (WHERE book_id > 1000000) AS generated_rows
FROM bookstore.books
UNION ALL
SELECT 'customers', COUNT(*), COUNT(*) FILTER (WHERE customer_id > 1000000)
FROM bookstore.customers
UNION ALL
SELECT 'orders', COUNT(*), COUNT(*) FILTER (WHERE order_id > 1000000)
FROM bookstore.orders
UNION ALL
SELECT 'order_items', COUNT(*), COUNT(*) FILTER (WHERE order_id > 1000000)
FROM bookstore.order_items
ORDER BY table_name;
