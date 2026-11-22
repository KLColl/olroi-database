BEGIN;

CREATE VIEW lab5.book_editor AS
SELECT
    b.book_id,
    b.isbn,
    b.title,
    a.first_name || ' ' || a.last_name AS author_name,
    c.category_name,
    b.price,
    b.stock_quantity
FROM bookstore.books b
JOIN bookstore.authors a USING (author_id)
JOIN bookstore.categories c USING (category_id);

-- Через представлення редагуються ціна та залишок базової таблиці.
CREATE RULE lab5_book_editor_update AS
ON UPDATE TO lab5.book_editor
DO INSTEAD
    UPDATE bookstore.books
    SET price = NEW.price,
        stock_quantity = NEW.stock_quantity
    WHERE book_id = OLD.book_id;

COMMIT;
