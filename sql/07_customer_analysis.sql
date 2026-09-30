-- =============================================================================
-- 07_customer_analysis.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : customer analysis
--
-- DEFINITIONS USED IN THIS FILE
--   registered customer : a row in `customers`
--   active customer     : a registered customer with at least one order
--   inactive customer   : a registered customer with no orders at all
--   repeat customer     : an active customer with MORE THAN ONE order
--   one-time customer   : an active customer with exactly one order
--   customer spend      : realised revenue, i.e. revenue from Completed orders
--   AOV                 : realised revenue / number of Completed orders
--
-- "Spend" always means realised revenue unless a query says otherwise. That
-- keeps every customer figure comparable with the headline business metrics.
-- =============================================================================

USE ecommerce_sales_analysis;


-- =============================================================================
-- 1. How many registered customers are there?
-- =============================================================================
SELECT COUNT(*) AS registered_customers
FROM customers;


-- =============================================================================
-- 2. Active customers  -  placed at least one order
-- =============================================================================
SELECT COUNT(DISTINCT customer_id) AS active_customers
FROM orders;


-- =============================================================================
-- 3. Inactive customers  -  never placed an order
-- =============================================================================
-- The LEFT JOIN keeps every customer, then keeps only the ones whose order side
-- is NULL. This is the standard "rows in A with no match in B" pattern.
SELECT COUNT(*) AS inactive_customers
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL;

-- The same figure the arithmetic way, as a cross-check.
SELECT (SELECT COUNT(*) FROM customers)
     - (SELECT COUNT(DISTINCT customer_id) FROM orders) AS inactive_customers_check;


-- =============================================================================
-- 4. Orders per customer, with spending and average order value
-- =============================================================================
-- Two things to notice:
--   * realised revenue is aggregated from order_items joined to orders
--   * AOV divides by Completed orders only, so a customer whose orders all
--     failed does not divide by zero. NULLIF turns 0 into NULL.
WITH customer_orders AS (
    SELECT o.customer_id,
           COUNT(DISTINCT o.order_id) AS orders_placed,
           COUNT(DISTINCT CASE WHEN o.status = 'Completed' THEN o.order_id END)
               AS completed_orders,
           ROUND(SUM(CASE WHEN o.status = 'Completed'
                          THEN oi.quantity * oi.unit_price
                               * (1 - oi.discount_percent / 100)
                          ELSE 0 END), 2) AS realised_revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    GROUP BY o.customer_id
)
SELECT c.customer_id,
       c.name,
       c.city,
       co.orders_placed,
       co.completed_orders,
       co.realised_revenue,
       ROUND(co.realised_revenue / NULLIF(co.completed_orders, 0), 2) AS avg_order_value
FROM customer_orders co
JOIN customers c ON c.customer_id = co.customer_id
ORDER BY co.orders_placed DESC, co.realised_revenue DESC
LIMIT 10;


-- =============================================================================
-- 5. Top customers by realised revenue
-- =============================================================================
SELECT c.customer_id,
       c.name,
       c.city,
       COUNT(DISTINCT o.order_id) AS completed_orders,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
WHERE o.status = 'Completed'
GROUP BY c.customer_id, c.name, c.city
ORDER BY realised_revenue DESC
LIMIT 10;


-- =============================================================================
-- 6. Repeat customer rate
-- =============================================================================
-- A customer is counted once, no matter how many orders they placed. The rate
-- is repeat customers divided by ACTIVE customers, because a customer who has
-- never ordered cannot possibly be a repeat buyer.
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS orders_placed
    FROM orders
    GROUP BY customer_id
)
SELECT COUNT(*)                                        AS active_customers,
       SUM(orders_placed > 1)                          AS repeat_customers,
       SUM(orders_placed = 1)                          AS one_time_customers,
       ROUND(100 * SUM(orders_placed > 1) / COUNT(*), 2) AS repeat_customer_rate_pct
FROM per_customer;

-- The same idea measured on value: how much of all orders comes from repeat
-- buyers?
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS orders_placed
    FROM orders
    GROUP BY customer_id
)
SELECT ROUND(100 * SUM(CASE WHEN pc.orders_placed > 1 THEN 1 ELSE 0 END)
                   / COUNT(*), 2) AS repeat_share_of_orders_pct
FROM orders o
JOIN per_customer pc ON pc.customer_id = o.customer_id;


-- =============================================================================
-- 7. Customer spending distribution  -  average, median, minimum, maximum
-- =============================================================================
-- MySQL has no MEDIAN() function. The portable trick is to number the rows in
-- order and pick the middle one; for an even count the two central values are
-- averaged. A median matters here because a handful of very large spenders
-- pull the average well above what a typical customer spends.
WITH customer_spend AS (
    SELECT o.customer_id,
           SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100))
               AS realised_revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'Completed'
    GROUP BY o.customer_id
),
ranked AS (
    SELECT realised_revenue,
           ROW_NUMBER() OVER (ORDER BY realised_revenue) AS row_num,
           COUNT(*)     OVER ()                          AS total_rows
    FROM customer_spend
)
SELECT COUNT(*)                                    AS customers_with_completed_orders,
       ROUND(AVG(realised_revenue), 2)             AS mean_spend,
       ROUND((SELECT AVG(realised_revenue)
              FROM ranked
              WHERE row_num IN (FLOOR((total_rows + 1) / 2),
                                CEIL((total_rows + 1) / 2))), 2) AS median_spend,
       ROUND(MIN(realised_revenue), 2)             AS min_spend,
       ROUND(MAX(realised_revenue), 2)             AS max_spend
FROM customer_spend;


-- =============================================================================
-- 8. Customers by city
-- =============================================================================
SELECT city,
       COUNT(*) AS registered_customers
FROM customers
GROUP BY city
ORDER BY registered_customers DESC;


-- =============================================================================
-- 9. Realised revenue by city
-- =============================================================================
-- The city here is the ORDER's shipping city, which is what the sales figures
-- should follow. It can differ from the customer's registered city.
SELECT o.shipping_city,
       COUNT(DISTINCT o.order_id) AS completed_orders,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100))
             / COUNT(DISTINCT o.order_id), 2)               AS avg_order_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'Completed'
GROUP BY o.shipping_city
ORDER BY realised_revenue DESC;


-- =============================================================================
-- 10. Customer lifetime-style summary
-- =============================================================================
-- For every customer who has ordered, show their first and last order, how long
-- they have been a buyer, how many orders they placed and their realised
-- revenue. This is a descriptive summary, NOT a formal CLV model: no
-- probability of churn, no future value projection, no discounting.
SELECT c.customer_id,
       c.name,
       c.city,
       MIN(o.order_date)                          AS first_order_date,
       MAX(o.order_date)                          AS last_order_date,
       DATEDIFF(MAX(o.order_date), MIN(o.order_date)) AS days_between_first_and_last,
       COUNT(DISTINCT o.order_id)                 AS orders_placed,
       ROUND(SUM(CASE WHEN o.status = 'Completed'
                      THEN oi.quantity * oi.unit_price
                           * (1 - oi.discount_percent / 100)
                      ELSE 0 END), 2)             AS realised_revenue
FROM customers c
JOIN orders o       ON o.customer_id = c.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY c.customer_id, c.name, c.city
ORDER BY realised_revenue DESC
LIMIT 10;
