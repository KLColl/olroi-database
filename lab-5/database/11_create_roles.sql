BEGIN;

CREATE ROLE lab5_reader NOLOGIN;
CREATE ROLE lab5_moderator NOLOGIN;
CREATE ROLE lab5_admin NOLOGIN;

GRANT lab5_reader TO lab5_moderator;
GRANT lab5_moderator TO lab5_admin;

GRANT CONNECT ON DATABASE bookstore_lab5 TO lab5_reader;
GRANT USAGE ON SCHEMA bookstore, lab5 TO lab5_reader;

GRANT SELECT ON
    bookstore.books,
    bookstore.authors,
    bookstore.categories,
    lab5.available_books,
    lab5.customer_sales,
    lab5.book_editor
TO lab5_reader;

GRANT SELECT, INSERT, UPDATE ON
    bookstore.books,
    bookstore.authors,
    bookstore.categories,
    bookstore.customers
TO lab5_moderator;

GRANT SELECT ON bookstore.orders, bookstore.order_items TO lab5_moderator;
GRANT INSERT ON bookstore.orders TO lab5_moderator;
GRANT UPDATE (price, stock_quantity) ON lab5.book_editor TO lab5_moderator;

GRANT USAGE, SELECT ON SEQUENCE
    bookstore.books_book_id_seq,
    bookstore.authors_author_id_seq,
    bookstore.categories_category_id_seq,
    bookstore.customers_customer_id_seq,
    bookstore.orders_order_id_seq
TO lab5_moderator;

GRANT EXECUTE ON PROCEDURE
    bookstore.set_order_item(BIGINT, BIGINT, INTEGER),
    bookstore.confirm_order(BIGINT),
    bookstore.cancel_order(BIGINT)
TO lab5_moderator;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA bookstore, lab5 TO lab5_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA bookstore, lab5 TO lab5_admin;
GRANT EXECUTE ON ALL ROUTINES IN SCHEMA bookstore, lab5 TO lab5_admin;
GRANT CREATE ON SCHEMA lab5 TO lab5_admin;

-- Права адміністратора також поширюються на об’єкти наступних етапів.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA lab5
GRANT ALL PRIVILEGES ON TABLES TO lab5_admin;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA lab5
GRANT ALL PRIVILEGES ON SEQUENCES TO lab5_admin;

CREATE ROLE lab5_viewer LOGIN PASSWORD 'Lab5Viewer2026!';
CREATE ROLE lab5_editor LOGIN PASSWORD 'Lab5Editor2026!';
CREATE ROLE lab5_administrator LOGIN PASSWORD 'Lab5Admin2026!';

GRANT lab5_reader TO lab5_viewer;
GRANT lab5_moderator TO lab5_editor;
GRANT lab5_admin TO lab5_administrator;

COMMIT;
