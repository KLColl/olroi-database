-- Виконати в bookstore_lab5 після перезапуску служби PostgreSQL.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA public;

SELECT
    current_database() AS database_name,
    current_setting('shared_preload_libraries') AS preload_libraries,
    current_setting('compute_query_id') AS compute_query_id,
    (
        SELECT extversion
        FROM pg_extension
        WHERE extname = 'pg_stat_statements'
    ) AS extension_version,
    (
        SELECT COUNT(*)
        FROM public.pg_stat_statements
        WHERE dbid = (
            SELECT oid
            FROM pg_database
            WHERE datname = current_database()
        )
    ) AS tracked_queries;
