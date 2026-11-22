BEGIN;

CREATE TABLE lab5.stock_alerts (
    book_id BIGINT PRIMARY KEY
        REFERENCES bookstore.books (book_id) ON DELETE CASCADE,
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity BETWEEN 0 AND 5),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION lab5.update_stock_alert()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF NEW.stock_quantity <= 5 THEN
        INSERT INTO lab5.stock_alerts (book_id, stock_quantity)
        VALUES (NEW.book_id, NEW.stock_quantity)
        ON CONFLICT (book_id) DO UPDATE
        SET stock_quantity = EXCLUDED.stock_quantity,
            updated_at = clock_timestamp();
    ELSE
        DELETE FROM lab5.stock_alerts WHERE book_id = NEW.book_id;
    END IF;

    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION lab5.update_stock_alert() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION lab5.update_stock_alert() TO lab5_admin;
GRANT SELECT ON lab5.stock_alerts TO lab5_moderator;

-- Зміна книги змінює попередження, а його тригер записує окрему подію аудиту.
CREATE TRIGGER lab5_stock_alerts_update
AFTER INSERT OR UPDATE OF stock_quantity ON bookstore.books
FOR EACH ROW EXECUTE FUNCTION lab5.update_stock_alert();

CREATE TRIGGER lab5_stock_alerts_audit
AFTER INSERT OR UPDATE OR DELETE ON lab5.stock_alerts
FOR EACH ROW EXECUTE FUNCTION lab5.log_data_change('book_id');

INSERT INTO lab5.stock_alerts (book_id, stock_quantity)
SELECT book_id, stock_quantity
FROM bookstore.books
WHERE stock_quantity <= 5;

COMMIT;
