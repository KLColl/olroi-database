BEGIN;
CREATE PROCEDURE bookstore.set_order_item(p_order_id BIGINT,p_book_id BIGINT,p_quantity INTEGER)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,bookstore AS $$
DECLARE v_status TEXT; v_price NUMERIC(10,2);
BEGIN
    IF p_quantity IS NULL OR p_quantity<=0 THEN RAISE EXCEPTION 'Кількість має бути додатною'; END IF;
    SELECT status INTO STRICT v_status FROM bookstore.orders WHERE order_id=p_order_id FOR UPDATE;
    IF v_status<>'Draft' THEN RAISE EXCEPTION 'Редагувати можна лише чернетку'; END IF;
    SELECT price INTO STRICT v_price FROM bookstore.books WHERE book_id=p_book_id FOR UPDATE;
    INSERT INTO bookstore.order_items(order_id,book_id,quantity,unit_price)
    VALUES(p_order_id,p_book_id,p_quantity,v_price)
    -- Повторне додавання змінює кількість, але зберігає початкову ціну продажу.
    ON CONFLICT(order_id,book_id) DO UPDATE SET quantity=EXCLUDED.quantity;
END $$;

CREATE PROCEDURE bookstore.confirm_order(p_order_id BIGINT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,bookstore AS $$
DECLARE v_status TEXT;
BEGIN
    SELECT status INTO STRICT v_status FROM bookstore.orders WHERE order_id=p_order_id FOR UPDATE;
    IF v_status<>'Draft' THEN RAISE EXCEPTION 'Підтвердити можна лише чернетку'; END IF;
    IF NOT EXISTS(SELECT 1 FROM bookstore.order_items WHERE order_id=p_order_id)
    THEN RAISE EXCEPTION 'Замовлення не містить позицій'; END IF;
    -- Однаковий порядок блокування книг зменшує ризик взаємного блокування замовлень.
    PERFORM b.book_id FROM bookstore.books b JOIN bookstore.order_items oi ON oi.book_id=b.book_id
    WHERE oi.order_id=p_order_id ORDER BY b.book_id FOR UPDATE OF b;
    -- Усі залишки перевіряються під блокуванням до першого списання.
    IF EXISTS(SELECT 1 FROM bookstore.order_items oi JOIN bookstore.books b ON b.book_id=oi.book_id
              WHERE oi.order_id=p_order_id AND oi.quantity>b.stock_quantity)
    THEN RAISE EXCEPTION 'Недостатньо товару на складі'; END IF;
    UPDATE bookstore.books b SET stock_quantity=b.stock_quantity-oi.quantity
    FROM bookstore.order_items oi WHERE oi.order_id=p_order_id AND oi.book_id=b.book_id;
    UPDATE bookstore.orders SET status='Confirmed',confirmed_at=clock_timestamp() WHERE order_id=p_order_id;
END $$;

CREATE PROCEDURE bookstore.cancel_order(p_order_id BIGINT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,bookstore AS $$
DECLARE v_status TEXT;
BEGIN
    SELECT status INTO STRICT v_status FROM bookstore.orders WHERE order_id=p_order_id FOR UPDATE;
    IF v_status='Cancelled' THEN RAISE EXCEPTION 'Замовлення вже скасоване'; END IF;
    -- Чернетка не списувала товар, тому повернення потрібне лише після підтвердження.
    IF v_status='Confirmed' THEN
        PERFORM b.book_id FROM bookstore.books b JOIN bookstore.order_items oi ON oi.book_id=b.book_id
        WHERE oi.order_id=p_order_id ORDER BY b.book_id FOR UPDATE OF b;
        UPDATE bookstore.books b SET stock_quantity=b.stock_quantity+oi.quantity
        FROM bookstore.order_items oi WHERE oi.order_id=p_order_id AND oi.book_id=b.book_id;
    END IF;
    UPDATE bookstore.orders SET status='Cancelled' WHERE order_id=p_order_id;
END $$;
REVOKE EXECUTE ON PROCEDURE bookstore.set_order_item(BIGINT,BIGINT,INTEGER),
    bookstore.confirm_order(BIGINT),bookstore.cancel_order(BIGINT) FROM PUBLIC;
COMMIT;
