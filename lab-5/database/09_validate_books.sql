BEGIN;

CREATE FUNCTION lab5.validate_book()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_checksum INTEGER := 0;
    v_position INTEGER;
BEGIN
    IF NEW.isbn IS NULL OR NEW.isbn !~ '^[0-9]{13}$' THEN
        RAISE EXCEPTION 'ISBN має містити рівно 13 цифр';
    END IF;

    FOR v_position IN 1..13 LOOP
        v_checksum := v_checksum
            + SUBSTRING(NEW.isbn FROM v_position FOR 1)::INTEGER
            * CASE WHEN v_position % 2 = 1 THEN 1 ELSE 3 END;
    END LOOP;

    IF v_checksum % 10 <> 0 THEN
        RAISE EXCEPTION 'Неправильна контрольна цифра ISBN-13';
    END IF;

    IF NEW.price IS NULL OR NEW.price < 0 THEN
        RAISE EXCEPTION 'Ціна має бути невід’ємною';
    END IF;

    IF NEW.stock_quantity IS NULL OR NEW.stock_quantity < 0 THEN
        RAISE EXCEPTION 'Залишок має бути невід’ємним';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER lab5_books_validate
BEFORE INSERT OR UPDATE OF isbn, price, stock_quantity ON bookstore.books
FOR EACH ROW EXECUTE FUNCTION lab5.validate_book();

COMMIT;
