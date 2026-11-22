EXPLAIN (ANALYZE, BUFFERS)
SELECT
    b.book_id,
    b.title,
    a.first_name || ' ' || a.last_name AS author_name,
    c.category_name,
    b.price,
    b.stock_quantity
FROM bookstore.books b
JOIN bookstore.authors a USING (author_id)
JOIN bookstore.categories c USING (category_id)
WHERE b.category_id = 3
  AND b.price BETWEEN 400 AND 600
  AND b.stock_quantity > 0
ORDER BY b.price, b.book_id
LIMIT 20;
