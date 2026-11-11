BEGIN;
CALL bookstore.set_order_item(1,1,3);
DO $$ DECLARE n BIGINT; BEGIN
    FOR n IN SELECT order_id FROM bookstore.orders ORDER BY order_id LIMIT 8 LOOP
        CALL bookstore.confirm_order(n);
    END LOOP;
END $$;
CALL bookstore.cancel_order(1);
COMMIT;
