SELECT current_database() AS database_name, 'bookstore.authors' AS object_name,
       COUNT(*) AS row_count FROM bookstore.authors
UNION ALL
SELECT current_database(), 'bookstore.categories', COUNT(*) FROM bookstore.categories
UNION ALL
SELECT current_database(), 'bookstore.books', COUNT(*) FROM bookstore.books
UNION ALL
SELECT current_database(), 'bookstore.customers', COUNT(*) FROM bookstore.customers
UNION ALL
SELECT current_database(), 'bookstore.orders', COUNT(*) FROM bookstore.orders
UNION ALL
SELECT current_database(), 'bookstore.order_items', COUNT(*) FROM bookstore.order_items
UNION ALL
SELECT current_database(), 'bookstore.app_users', COUNT(*) FROM bookstore.app_users
UNION ALL
SELECT current_database(), 'bookstore.activity_log', COUNT(*) FROM bookstore.activity_log
UNION ALL
SELECT current_database(), 'lab5.dataset_info', COUNT(*) FROM lab5.dataset_info
UNION ALL
SELECT current_database(), 'lab5.audit_log', COUNT(*) FROM lab5.audit_log
UNION ALL
SELECT current_database(), 'lab5.stock_alerts', COUNT(*) FROM lab5.stock_alerts
UNION ALL
SELECT current_database(), 'lab5.maintenance_log', COUNT(*) FROM lab5.maintenance_log
UNION ALL
SELECT current_database(), 'lab5.category_summary', COUNT(*) FROM lab5.category_summary
ORDER BY object_name;
