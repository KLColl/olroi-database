BEGIN;
CREATE TABLE bookstore.activity_log (
    log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT,
    username TEXT NOT NULL DEFAULT session_user,
    action TEXT NOT NULL CHECK(action IN ('INSERT','UPDATE','DELETE','READ','LOGIN','LOGOUT','REGISTER','EXPORT','BACKUP')),
    table_name TEXT NOT NULL,
    record_key JSONB NOT NULL DEFAULT '{}'::JSONB,
    old_data JSONB,
    new_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE bookstore.books ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
CREATE FUNCTION bookstore.touch_book_timestamp() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at:=clock_timestamp(); RETURN NEW; END $$;

CREATE FUNCTION bookstore.audit_data_change() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,bookstore AS $$
DECLARE v_old JSONB; v_new JSONB; v_key JSONB:='{}'::JSONB; v_column TEXT;
        v_user_id BIGINT; v_username TEXT;
BEGIN
    -- Секретні хеші вилучаються до формування знімків журналу.
    IF TG_OP<>'INSERT' THEN v_old:=to_jsonb(OLD)-'password_hash'-'api_key_hash'-'api_token_hash'; END IF;
    IF TG_OP<>'DELETE' THEN v_new:=to_jsonb(NEW)-'password_hash'-'api_key_hash'-'api_token_hash'; END IF;
    FOREACH v_column IN ARRAY TG_ARGV LOOP
        v_key:=v_key||jsonb_build_object(v_column,COALESCE(v_new->v_column,v_old->v_column));
    END LOOP;
    v_user_id:=NULLIF(current_setting('app.user_id',TRUE),'')::BIGINT;
    v_username:=COALESCE(NULLIF(current_setting('app.username',TRUE),''),session_user);
    INSERT INTO bookstore.activity_log(user_id,username,action,table_name,record_key,old_data,new_data)
    VALUES(v_user_id,v_username,TG_OP,TG_TABLE_NAME,v_key,v_old,v_new);
    RETURN NULL;
END $$;
CREATE TRIGGER books_touch_timestamp BEFORE UPDATE ON bookstore.books
FOR EACH ROW EXECUTE FUNCTION bookstore.touch_book_timestamp();
CREATE TRIGGER authors_audit AFTER INSERT OR UPDATE OR DELETE ON bookstore.authors
FOR EACH ROW EXECUTE FUNCTION bookstore.audit_data_change('author_id');
CREATE TRIGGER categories_audit AFTER INSERT OR UPDATE OR DELETE ON bookstore.categories
FOR EACH ROW EXECUTE FUNCTION bookstore.audit_data_change('category_id');
CREATE TRIGGER books_audit AFTER INSERT OR UPDATE OR DELETE ON bookstore.books
FOR EACH ROW EXECUTE FUNCTION bookstore.audit_data_change('book_id');
CREATE TRIGGER customers_audit AFTER INSERT OR UPDATE OR DELETE ON bookstore.customers
FOR EACH ROW EXECUTE FUNCTION bookstore.audit_data_change('customer_id');
CREATE TRIGGER orders_audit AFTER INSERT OR UPDATE OR DELETE ON bookstore.orders
FOR EACH ROW EXECUTE FUNCTION bookstore.audit_data_change('order_id');
CREATE TRIGGER order_items_audit AFTER INSERT OR UPDATE OR DELETE ON bookstore.order_items
FOR EACH ROW EXECUTE FUNCTION bookstore.audit_data_change('order_id','book_id');
COMMIT;
