-- =============================================================================
-- 11_advanced_analysis.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : advanced SQL
--
-- TECHNIQUES DEMONSTRATED
--   common table expressions (CTEs), derived tables, scalar subqueries,
--   correlated subqueries, CASE expressions, window functions
--   (ROW_NUMBER, RANK, DENSE_RANK, LAG, SUM OVER), running totals,
--   month-over-month change, percentage contribution and ranking.
--
-- All revenue here is REALISED (Completed orders only) unless stated otherwise.
-- =============================================================================

USE ecommerce_sales_analysis;


-- =============================================================================
-- 1. Category revenue contribution
--    CTE + window function: each category's share of the total, its rank, and a
--    running cumulative share so concentration is visible at a glance.
-- =============================================================================
WITH category_revenue AS (
    SELECT pr.category,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS revenue
    FROM order_items oi
    JOIN products pr ON pr.product_id = oi.product_id
    JOIN orders o    ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY pr.category
)
SELECT category,
       ROUND(revenue, 2)                                          AS realised_revenue,
       ROUND(100 * revenue / SUM(revenue) OVER (), 2)             AS pct_of_total,
       RANK() OVER (ORDER BY revenue DESC)                        AS revenue_rank,
       ROUND(100 * SUM(revenue) OVER (ORDER BY revenue DESC)
             / SUM(revenue) OVER (), 2)                           AS cumulative_pct
FROM category_revenue
ORDER BY revenue DESC;


-- =============================================================================
-- 2. Top 3 products in every category
--    ROW_NUMBER() partitioned by category. A plain GROUP BY cannot do this,
--    because the "top N per group" question needs a rank inside each group.
-- =============================================================================
WITH product_revenue AS (
    SELECT pr.category,
           pr.product_name,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS revenue
    FROM order_items oi
    JOIN products pr ON pr.product_id = oi.product_id
    JOIN orders o    ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY pr.category, pr.product_id, pr.product_name
),
ranked AS (
    SELECT category,
           product_name,
           revenue,
           ROW_NUMBER() OVER (PARTITION BY category
                              ORDER BY revenue DESC) AS position_in_category
    FROM product_revenue
)
SELECT category,
       position_in_category,
       product_name,
       ROUND(revenue, 2) AS realised_revenue
FROM ranked
WHERE position_in_category <= 3
ORDER BY category, position_in_category;


-- =============================================================================
-- 3. ROW_NUMBER vs RANK vs DENSE_RANK
--    Ranked by number of orders placed. Order counts are integers, so ties are
--    common and the three functions visibly disagree:
--      ROW_NUMBER  - always 1,2,3,4... even across a tie
--      RANK        - equal values share a rank, then the next rank is skipped
--      DENSE_RANK  - equal values share a rank, and the next rank is not skipped
-- =============================================================================
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS orders_placed
    FROM orders
    GROUP BY customer_id
)
SELECT customer_id,
       orders_placed,
       ROW_NUMBER() OVER (ORDER BY orders_placed DESC) AS row_number_value,
       RANK()       OVER (ORDER BY orders_placed DESC) AS rank_value,
       DENSE_RANK() OVER (ORDER BY orders_placed DESC) AS dense_rank_value
FROM per_customer
ORDER BY orders_placed DESC
LIMIT 15;


-- =============================================================================
-- 4. Monthly revenue with running total and month-over-month change
--    LAG() looks one month back. 2026-09 is a partial month, so it is excluded
--    here to avoid a misleading drop.
-- =============================================================================
WITH monthly AS (
    SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'Completed'
      AND o.order_date < '2026-09-01'
    GROUP BY month
)
SELECT month,
       ROUND(revenue, 2)                                    AS realised_revenue,
       ROUND(SUM(revenue) OVER (ORDER BY month), 2)         AS cumulative_revenue,
       ROUND(revenue - LAG(revenue) OVER (ORDER BY month), 2) AS mom_change,
       ROUND(100 * (revenue / LAG(revenue) OVER (ORDER BY month) - 1), 2)
                                                            AS mom_change_pct
FROM monthly
ORDER BY month;


-- =============================================================================
-- 5. First six complete months versus last six complete months
--    A single-row comparison that answers "is the business growing?" using only
--    complete months. This reproduces the Phase 2 trend finding.
-- =============================================================================
WITH monthly AS (
    SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'Completed'
      AND o.order_date < '2026-09-01'
    GROUP BY month
),
numbered AS (
    SELECT month,
           revenue,
           ROW_NUMBER() OVER (ORDER BY month) AS month_number,
           COUNT(*)     OVER ()               AS total_months
    FROM monthly
)
SELECT COUNT(*)                                              AS complete_months,
       ROUND(AVG(CASE WHEN month_number <= 6 THEN revenue END), 2)
                                                             AS first_6_avg,
       ROUND(AVG(CASE WHEN month_number > total_months - 6 THEN revenue END), 2)
                                                             AS last_6_avg,
       ROUND(100 * (AVG(CASE WHEN month_number > total_months - 6 THEN revenue END)
                    / AVG(CASE WHEN month_number <= 6 THEN revenue END) - 1), 2)
                                                             AS pct_change
FROM numbered;


-- =============================================================================
-- 6. Customer ranking by realised spend, with cumulative revenue share
--    The running total shows how concentrated spending really is. If the top 10
--    customers hold 3.6% of revenue, the customer base is broad, not dependent
--    on a handful of whales.
-- =============================================================================
WITH customer_spend AS (
    SELECT o.customer_id,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS realised_spend
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'Completed'
    GROUP BY o.customer_id
)
SELECT RANK() OVER (ORDER BY realised_spend DESC)   AS spend_rank,
       customer_id,
       ROUND(realised_spend, 2)                     AS realised_spend,
       ROUND(100 * SUM(realised_spend) OVER (ORDER BY realised_spend DESC)
             / SUM(realised_spend) OVER (), 2)      AS cumulative_pct_of_total
FROM customer_spend
ORDER BY realised_spend DESC
LIMIT 20;


-- =============================================================================
-- 7. Repeat customer classification
--    Explicit definition: 1 order = One-time, 2 or more orders = Repeat.
--    Percentages are of ACTIVE customers (those with at least one order).
-- =============================================================================
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS orders_placed
    FROM orders
    GROUP BY customer_id
)
SELECT CASE WHEN orders_placed = 1 THEN 'One-time' ELSE 'Repeat' END AS customer_type,
       COUNT(*)                                                       AS customers,
       SUM(orders_placed)                                             AS orders_placed,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)               AS pct_of_active_customers
FROM per_customer
GROUP BY customer_type
ORDER BY customers DESC;


-- =============================================================================
-- 8. Correlated subquery - products priced above their own category average
--    The inner query runs once per outer row and reads the outer row's category,
--    which is what makes it correlated.
-- =============================================================================
SELECT p.product_id,
       p.product_name,
       p.category,
       p.price,
       (SELECT ROUND(AVG(p2.price), 2)
        FROM products p2
        WHERE p2.category = p.category) AS category_avg_price
FROM products p
WHERE p.price > (SELECT AVG(p3.price)
                 FROM products p3
                 WHERE p3.category = p.category)
ORDER BY p.category, p.price DESC
LIMIT 15;


-- =============================================================================
-- 9. Correlated subquery - customers spending above their city average
--    Answers "who is unusually valuable for their city?", not just "who spends
--    most", which is what a city-level marketing decision actually needs.
-- =============================================================================
WITH customer_spend AS (
    SELECT o.customer_id,
           c.city,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS realised_spend
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    JOIN customers c    ON c.customer_id = o.customer_id
    WHERE o.status = 'Completed'
    GROUP BY o.customer_id, c.city
)
SELECT customer_id,
       city,
       ROUND(realised_spend, 2) AS realised_spend,
       (SELECT ROUND(AVG(cs2.realised_spend), 2)
        FROM customer_spend cs2
        WHERE cs2.city = cs.city) AS city_avg_spend
FROM customer_spend cs
WHERE realised_spend > (SELECT AVG(cs3.realised_spend)
                        FROM customer_spend cs3
                        WHERE cs3.city = cs.city)
ORDER BY realised_spend DESC
LIMIT 15;


-- =============================================================================
-- 10. Derived table - best revenue month inside each year
--     The inner SELECT builds one row per month and numbers the months inside
--     each year, newest revenue first. The outer query then keeps row 1 only.
--     This is the "top N per group" pattern written without a self-join.
-- =============================================================================
SELECT year,
       month,
       ROUND(revenue, 2) AS best_month_revenue
FROM (
    SELECT YEAR(o.order_date)                    AS year,
           DATE_FORMAT(o.order_date, '%Y-%m')    AS month,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS revenue,
           ROW_NUMBER() OVER (PARTITION BY YEAR(o.order_date)
                              ORDER BY SUM(oi.quantity * oi.unit_price
                                           * (1 - oi.discount_percent / 100)) DESC)
                                                AS month_rank
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'Completed'
    GROUP BY year, month
) AS ranked_months
WHERE month_rank = 1
ORDER BY year;


-- =============================================================================
-- 11. Busiest and quietest COMPLETE month
--     The data ends on 2026-09-26, so 2026-09 is a partial month. Ranking months
--     without excluding it would make 2026-09 look like the worst month in the
--     dataset, when in fact it is simply unfinished. The cut-off below is the
--     same '2026-09-01' boundary used in sections 4 and 5 and in
--     13_phase2_reconciliation.sql, so every month-based figure in this project
--     is computed on the same set of complete months.
-- =============================================================================
WITH complete_months AS (
    SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
           COUNT(*)                           AS orders,
           SUM(o.status = 'Completed')        AS completed_orders
    FROM orders o
    WHERE o.order_date < '2026-09-01'
    GROUP BY month
)
SELECT 'busiest' AS label, month, orders, completed_orders
FROM complete_months
ORDER BY orders DESC
LIMIT 1;

WITH complete_months AS (
    SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
           COUNT(*)                           AS orders,
           SUM(o.status = 'Completed')        AS completed_orders
    FROM orders o
    WHERE o.order_date < '2026-09-01'
    GROUP BY month
)
SELECT 'quietest' AS label, month, orders, completed_orders
FROM complete_months
ORDER BY orders ASC
LIMIT 1;
