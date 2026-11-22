EXPLAIN (ANALYZE, BUFFERS)
SELECT
    o.confirmed_at::DATE AS sale_date,
    COUNT(DISTINCT o.order_id) AS confirmed_orders,
    SUM(oi.quantity) AS sold_copies,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM bookstore.orders o
JOIN bookstore.order_items oi USING (order_id)
WHERE o.status = 'Confirmed'
  AND o.confirmed_at >= (
      SELECT loaded_at FROM lab5.dataset_info
  ) - INTERVAL '1 day'
  AND o.confirmed_at < (
      SELECT loaded_at FROM lab5.dataset_info
  )
GROUP BY o.confirmed_at::DATE
ORDER BY sale_date;
