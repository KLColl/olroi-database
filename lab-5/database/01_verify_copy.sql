SELECT
    current_database() AS database_name,
    'authors' AS table_name,
    COUNT(*) AS row_count
FROM bookstore.authors
UNION ALL
SELECT current_database(), 'categories', COUNT(*) FROM bookstore.categories
UNION ALL
SELECT current_database(), 'books', COUNT(*) FROM bookstore.books
UNION ALL
SELECT current_database(), 'customers', COUNT(*) FROM bookstore.customers
UNION ALL
SELECT current_database(), 'orders', COUNT(*) FROM bookstore.orders
UNION ALL
SELECT current_database(), 'order_items', COUNT(*) FROM bookstore.order_items
UNION ALL
SELECT current_database(), 'app_users', COUNT(*) FROM bookstore.app_users
UNION ALL
SELECT current_database(), 'activity_log', COUNT(*) FROM bookstore.activity_log
ORDER BY table_name;
