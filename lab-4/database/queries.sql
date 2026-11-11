-- Основні запити
SELECT title,author_name,price,stock_quantity FROM bookstore.book_catalog
WHERE price BETWEEN 300 AND 450 AND stock_quantity>=15 ORDER BY price DESC,title;

SELECT b.title,a.first_name||' '||a.last_name AS author,c.category_name,b.price
FROM bookstore.books b JOIN bookstore.authors a USING(author_id)
JOIN bookstore.categories c USING(category_id) ORDER BY b.title;

SELECT c.category_name,COUNT(b.book_id) AS book_titles,
       COALESCE(SUM(b.stock_quantity),0) AS available_copies,
       ROUND(AVG(b.price),2) AS average_price,
       COALESCE(SUM(b.price*b.stock_quantity),0) AS inventory_value
FROM bookstore.categories c LEFT JOIN bookstore.books b USING(category_id)
GROUP BY c.category_id,c.category_name ORDER BY inventory_value DESC;

SELECT title,author_name,price FROM bookstore.book_catalog
WHERE price>(SELECT AVG(price) FROM bookstore.books) ORDER BY price DESC;

SELECT c.customer_id,c.full_name,c.email FROM bookstore.customers c
WHERE NOT EXISTS(SELECT 1 FROM bookstore.orders o WHERE o.customer_id=c.customer_id
                 AND o.status='Confirmed') ORDER BY c.customer_id;

-- Аналітика 1: категорії, склад і рейтинг продажів без множення залишків через JOIN
WITH category_sales AS (
    SELECT b.category_id,COUNT(DISTINCT o.order_id) AS orders_count,
           SUM(oi.quantity) AS sold_copies,SUM(oi.quantity*oi.unit_price) AS revenue
    FROM bookstore.order_items oi JOIN bookstore.orders o USING(order_id)
    JOIN bookstore.books b USING(book_id) WHERE o.status='Confirmed' GROUP BY b.category_id
), catalog_stats AS (
    -- Склад агрегується окремо, щоб кілька продажів книги не множили її залишок.
    SELECT category_id,COUNT(*) AS book_titles,SUM(stock_quantity) AS available_copies
    FROM bookstore.books GROUP BY category_id
)
SELECT c.category_name,COALESCE(cs.book_titles,0) AS book_titles,
       COALESCE(cs.available_copies,0) AS available_copies,
       COALESCE(s.orders_count,0) AS orders_count,COALESCE(s.sold_copies,0) AS sold_copies,
       COALESCE(s.revenue,0) AS revenue,
       DENSE_RANK() OVER(ORDER BY COALESCE(s.revenue,0) DESC) AS revenue_rank
FROM bookstore.categories c LEFT JOIN category_sales s USING(category_id)
LEFT JOIN catalog_stats cs USING(category_id) ORDER BY revenue_rank,c.category_name;

-- Аналітика 2: покупці та частка в продажах
WITH customer_statistics AS (
    SELECT c.customer_id,c.full_name,COUNT(s.order_id) AS total_orders,
           COUNT(s.order_id) FILTER(WHERE s.status='Confirmed') AS confirmed_orders,
           COUNT(s.order_id) FILTER(WHERE s.status='Cancelled') AS cancelled_orders,
           COALESCE(SUM(s.order_total) FILTER(WHERE s.status='Confirmed'),0) AS total_spent
    FROM bookstore.customers c LEFT JOIN bookstore.order_summary s USING(customer_id)
    GROUP BY c.customer_id,c.full_name
)
SELECT *,ROUND(100.0*total_spent/NULLIF(SUM(total_spent) OVER(),0),2) AS revenue_share_percent,
       DENSE_RANK() OVER(ORDER BY total_spent DESC) AS customer_rank
FROM customer_statistics ORDER BY customer_rank,full_name;

-- Аналітика 3: календар, дні без продажів та рухомий підсумок
WITH calendar AS (
    SELECT day::DATE AS sale_date FROM generate_series(
        CURRENT_DATE-INTERVAL '13 days',CURRENT_DATE,INTERVAL '1 day') dates(day)
), daily_sales AS (
    SELECT confirmed_at::DATE AS sale_date,COUNT(*) AS confirmed_orders,SUM(order_total) AS revenue
    FROM bookstore.order_summary WHERE status='Confirmed'
      AND confirmed_at>=CURRENT_DATE-INTERVAL '13 days'
      AND confirmed_at<CURRENT_DATE+INTERVAL '1 day' GROUP BY confirmed_at::DATE
), filled_days AS (
    SELECT c.sale_date,COALESCE(s.confirmed_orders,0) AS confirmed_orders,
           COALESCE(s.revenue,0) AS revenue
    FROM calendar c LEFT JOIN daily_sales s USING(sale_date)
)
SELECT *,SUM(revenue) OVER(ORDER BY sale_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
    AS seven_day_revenue FROM filled_days ORDER BY sale_date;

EXPLAIN(ANALYZE,BUFFERS)
SELECT book_id,title,price,stock_quantity FROM bookstore.books
WHERE category_id=3 AND price>=300 ORDER BY price,book_id LIMIT 5;

-- Підсумкові кількості всіх таблиць
SELECT 'authors' AS table_name,COUNT(*) AS row_count FROM bookstore.authors
UNION ALL SELECT 'categories',COUNT(*) FROM bookstore.categories
UNION ALL SELECT 'books',COUNT(*) FROM bookstore.books
UNION ALL SELECT 'customers',COUNT(*) FROM bookstore.customers
UNION ALL SELECT 'orders',COUNT(*) FROM bookstore.orders
UNION ALL SELECT 'order_items',COUNT(*) FROM bookstore.order_items
UNION ALL SELECT 'app_users',COUNT(*) FROM bookstore.app_users
UNION ALL SELECT 'activity_log',COUNT(*) FROM bookstore.activity_log
ORDER BY table_name;
