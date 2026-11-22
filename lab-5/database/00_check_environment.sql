SELECT
    current_database() AS database_name,
    current_user AS database_user,
    current_setting('server_version') AS postgresql_version,
    to_regclass('bookstore.books') AS books_table,
    to_regclass('bookstore.orders') AS orders_table,
    to_regclass('bookstore.order_items') AS order_items_table,
    current_setting('shared_preload_libraries') AS preload_libraries,
    EXISTS (
        SELECT 1
        FROM pg_available_extensions
        WHERE name = 'pg_stat_statements'
    ) AS statistics_extension_available;
