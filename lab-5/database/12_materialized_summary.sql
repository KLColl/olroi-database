BEGIN;

CREATE MATERIALIZED VIEW lab5.category_summary AS
WITH stock AS (
    SELECT
        b.category_id,
        COUNT(*) AS book_titles,
        SUM(b.stock_quantity) AS available_copies,
        SUM(b.price * b.stock_quantity) AS inventory_value
    FROM bookstore.books b
    GROUP BY b.category_id
), sales AS (
    SELECT
        b.category_id,
        COUNT(DISTINCT o.order_id) AS confirmed_orders,
        SUM(oi.quantity) AS sold_copies,
        SUM(oi.quantity * oi.unit_price) AS revenue
    FROM bookstore.orders o
    JOIN bookstore.order_items oi USING (order_id)
    JOIN bookstore.books b USING (book_id)
    WHERE o.status = 'Confirmed'
    GROUP BY b.category_id
)
SELECT
    c.category_id,
    c.category_name,
    COALESCE(s.book_titles, 0) AS book_titles,
    COALESCE(s.available_copies, 0) AS available_copies,
    COALESCE(s.inventory_value, 0) AS inventory_value,
    COALESCE(p.confirmed_orders, 0) AS confirmed_orders,
    COALESCE(p.sold_copies, 0) AS sold_copies,
    COALESCE(p.revenue, 0) AS revenue
FROM bookstore.categories c
LEFT JOIN stock s USING (category_id)
LEFT JOIN sales p USING (category_id);

CREATE UNIQUE INDEX lab5_category_summary_pk
ON lab5.category_summary (category_id);

CREATE FUNCTION lab5.refresh_category_summary()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    -- Повне оновлення виконується один раз після оператора зміни даних.
    REFRESH MATERIALIZED VIEW lab5.category_summary;
    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION lab5.refresh_category_summary() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION lab5.refresh_category_summary() TO lab5_admin;
GRANT SELECT ON lab5.category_summary TO lab5_reader;

CREATE TRIGGER lab5_refresh_books
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON bookstore.books
FOR EACH STATEMENT EXECUTE FUNCTION lab5.refresh_category_summary();

CREATE TRIGGER lab5_refresh_orders
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON bookstore.orders
FOR EACH STATEMENT EXECUTE FUNCTION lab5.refresh_category_summary();

CREATE TRIGGER lab5_refresh_items
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON bookstore.order_items
FOR EACH STATEMENT EXECUTE FUNCTION lab5.refresh_category_summary();

CREATE TRIGGER lab5_refresh_categories
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON bookstore.categories
FOR EACH STATEMENT EXECUTE FUNCTION lab5.refresh_category_summary();

COMMIT;
