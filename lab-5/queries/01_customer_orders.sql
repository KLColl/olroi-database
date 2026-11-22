EXPLAIN (ANALYZE, BUFFERS)
SELECT
    o.order_id,
    c.full_name,
    o.created_at,
    o.status,
    COUNT(oi.book_id) AS book_titles,
    COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS order_total
FROM bookstore.orders o
JOIN bookstore.customers c USING (customer_id)
LEFT JOIN bookstore.order_items oi USING (order_id)
WHERE o.customer_id = 1000500
  AND o.created_at >= (
      SELECT loaded_at FROM lab5.dataset_info
  ) - INTERVAL '365 days'
GROUP BY o.order_id, c.customer_id, c.full_name
ORDER BY o.created_at DESC, o.order_id DESC
LIMIT 20;
