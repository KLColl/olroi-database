BEGIN;

CREATE TABLE lab5.maintenance_log (
    log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('ANALYZE', 'REINDEX')),
    object_name TEXT NOT NULL,
    duration_ms NUMERIC(14, 3) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    executed_by TEXT NOT NULL
);

CREATE PROCEDURE lab5.maintain_database()
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    v_object RECORD;
    v_started TIMESTAMPTZ;
    v_run_id UUID := gen_random_uuid();
    v_actor TEXT := COALESCE(
        NULLIF(current_setting('role', TRUE), 'none'), session_user
    );
BEGIN
    FOR v_object IN
        SELECT n.nspname AS schema_name, c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('bookstore', 'lab5')
          AND c.relkind IN ('r', 'm')
          AND NOT (
              n.nspname = 'lab5' AND c.relname = 'maintenance_log'
          )
        ORDER BY n.nspname, c.relname
    LOOP
        v_started := clock_timestamp();
        EXECUTE format(
            'ANALYZE %I.%I', v_object.schema_name, v_object.table_name
        );

        INSERT INTO lab5.maintenance_log (
            run_id, operation, object_name, duration_ms, executed_by
        )
        VALUES (
            v_run_id, 'ANALYZE',
            format('%I.%I', v_object.schema_name, v_object.table_name),
            ROUND(EXTRACT(EPOCH FROM (clock_timestamp() - v_started)) * 1000, 3),
            v_actor
        );

        v_started := clock_timestamp();
        -- Звичайний REINDEX TABLE дозволено виконувати в транзакції процедури.
        EXECUTE format(
            'REINDEX TABLE %I.%I', v_object.schema_name, v_object.table_name
        );

        INSERT INTO lab5.maintenance_log (
            run_id, operation, object_name, duration_ms, executed_by
        )
        VALUES (
            v_run_id, 'REINDEX',
            format('%I.%I', v_object.schema_name, v_object.table_name),
            ROUND(EXTRACT(EPOCH FROM (clock_timestamp() - v_started)) * 1000, 3),
            v_actor
        );
    END LOOP;

    RAISE NOTICE 'Обслуговування завершено. Ідентифікатор запуску: %', v_run_id;
END;
$$;

REVOKE ALL ON PROCEDURE lab5.maintain_database() FROM PUBLIC;
GRANT EXECUTE ON PROCEDURE lab5.maintain_database() TO lab5_admin;

COMMIT;
