-- Виконати окремо, з увімкненим Auto-commit, після перевірки порожнього shared_preload_libraries.
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
