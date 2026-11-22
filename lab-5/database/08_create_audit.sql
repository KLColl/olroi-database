BEGIN;

CREATE TABLE lab5.audit_log (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    operation TEXT NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    table_name TEXT NOT NULL,
    record_key JSONB NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    login_user TEXT NOT NULL,
    changed_by TEXT NOT NULL
);

CREATE INDEX lab5_audit_table_time_idx
ON lab5.audit_log (table_name, changed_at DESC);

CREATE FUNCTION lab5.log_data_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    v_old JSONB;
    v_new JSONB;
    v_key JSONB := '{}'::JSONB;
    v_column TEXT;
    v_actor TEXT;
BEGIN
    -- Хеші паролів і токенів вилучаються до запису історичних знімків.
    IF TG_OP <> 'INSERT' THEN
        v_old := to_jsonb(OLD) - 'password_hash' - 'api_token_hash' - 'api_key_hash';
    END IF;

    IF TG_OP <> 'DELETE' THEN
        v_new := to_jsonb(NEW) - 'password_hash' - 'api_token_hash' - 'api_key_hash';
    END IF;

    FOREACH v_column IN ARRAY TG_ARGV LOOP
        v_key := v_key || jsonb_build_object(
            v_column, COALESCE(v_new -> v_column, v_old -> v_column)
        );
    END LOOP;

    -- Усередині SECURITY DEFINER current_user є власником функції.
    -- Зберігаємо окремо логін з’єднання та роль, обрану через SET ROLE.
    v_actor := COALESCE(
        NULLIF(current_setting('role', TRUE), 'none'), session_user
    );

    INSERT INTO lab5.audit_log (
        operation, table_name, record_key, old_values, new_values,
        login_user, changed_by
    )
    VALUES (
        TG_OP, TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
        v_key, v_old, v_new, session_user, v_actor
    );

    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION lab5.log_data_change() FROM PUBLIC;

CREATE TRIGGER lab5_books_audit
AFTER INSERT OR UPDATE OR DELETE ON bookstore.books
FOR EACH ROW EXECUTE FUNCTION lab5.log_data_change('book_id');

CREATE TRIGGER lab5_authors_audit
AFTER INSERT OR UPDATE OR DELETE ON bookstore.authors
FOR EACH ROW EXECUTE FUNCTION lab5.log_data_change('author_id');

CREATE TRIGGER lab5_categories_audit
AFTER INSERT OR UPDATE OR DELETE ON bookstore.categories
FOR EACH ROW EXECUTE FUNCTION lab5.log_data_change('category_id');

CREATE TRIGGER lab5_customers_audit
AFTER INSERT OR UPDATE OR DELETE ON bookstore.customers
FOR EACH ROW EXECUTE FUNCTION lab5.log_data_change('customer_id');

CREATE TRIGGER lab5_orders_audit
AFTER INSERT OR UPDATE OR DELETE ON bookstore.orders
FOR EACH ROW EXECUTE FUNCTION lab5.log_data_change('order_id');

CREATE TRIGGER lab5_items_audit
AFTER INSERT OR UPDATE OR DELETE ON bookstore.order_items
FOR EACH ROW EXECUTE FUNCTION lab5.log_data_change('order_id', 'book_id');

CREATE TRIGGER lab5_users_audit
AFTER INSERT OR UPDATE OR DELETE ON bookstore.app_users
FOR EACH ROW EXECUTE FUNCTION lab5.log_data_change('user_id');

COMMIT;
