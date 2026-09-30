-- =============================================================================
-- 10_business_questions.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : the twenty portfolio questions
--
-- Every question states the metric it uses, because the same words can mean
-- different things. Unless a question says otherwise:
--   revenue / profit / spend = REALISED (Completed orders only)
--   "units"                  = every order line, whatever the order status
--   "orders"                 = rows in `orders`
-- =============================================================================

USE ecommerce_sales_analysis;


-- =============================================================================
-- Q1. Which product categories generate the most realised revenue?
-- Metric: SUM(quantity * unit_price * (1 - discount/100)) on Completed orders.
-- =============================================================================
SELECT pr.category,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue,
       ROUND(100 * SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100))
             / (SELECT SUM(oi2.quantity * oi2.unit_price
                           * (1 - oi2.discount_percent / 100))
                FROM order_items oi2
                JOIN orders o2 ON o2.order_id = oi2.order_id
                WHERE o2.status = 'Completed'), 2) AS pct_of_total
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.category
ORDER BY realised_revenue DESC;


-- =============================================================================
-- Q2. Which categories generate the most profit?
-- Metric: Q1 revenue - SUM(quantity * products.cost). Discount lowers revenue
-- but never lowers cost, so margin bleeds when discounts are deep.
-- =============================================================================
SELECT pr.category,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)
                 - oi.quantity * pr.cost), 2) AS realised_profit
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.category
ORDER BY realised_profit DESC;


-- =============================================================================
-- Q3. Which products sell the most units?
-- Metric: SUM(quantity). Both bases shown - see 08_product_analysis.sql.
-- =============================================================================
SELECT pr.product_name,
       pr.category,
       SUM(oi.quantity) AS units_all_orders,
       SUM(CASE WHEN o.status = 'Completed' THEN oi.quantity ELSE 0 END)
                        AS units_completed_orders
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
GROUP BY pr.product_id, pr.product_name, pr.category
ORDER BY units_all_orders DESC
LIMIT 5;


-- =============================================================================
-- Q4. Which products generate the most revenue?
-- Metric: realised revenue by product.
-- =============================================================================
SELECT pr.product_name,
       pr.category,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.product_id, pr.product_name, pr.category
ORDER BY realised_revenue DESC
LIMIT 5;


-- =============================================================================
-- Q5. Which cities generate the most realised revenue?
-- Metric: realised revenue grouped by the order's shipping city.
-- =============================================================================
SELECT o.shipping_city,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'Completed'
GROUP BY o.shipping_city
ORDER BY realised_revenue DESC
LIMIT 5;


-- =============================================================================
-- Q6. Which customers spend the most?
-- Metric: realised revenue per customer.
-- =============================================================================
SELECT c.customer_id,
       c.name,
       c.city,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_spend
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
WHERE o.status = 'Completed'
GROUP BY c.customer_id, c.name, c.city
ORDER BY realised_spend DESC
LIMIT 10;


-- =============================================================================
-- Q7. What percentage of customers are repeat customers?
-- Definition: repeat = an active customer (>= 1 order) with MORE THAN ONE order.
-- The denominator is active customers, not all registered customers.
-- =============================================================================
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS orders_placed
    FROM orders
    GROUP BY customer_id
)
SELECT COUNT(*)                                          AS active_customers,
       SUM(orders_placed > 1)                            AS repeat_customers,
       ROUND(100 * SUM(orders_placed > 1) / COUNT(*), 2) AS repeat_customer_rate_pct
FROM per_customer;


-- =============================================================================
-- Q8. What is the monthly revenue trend?
-- Metric: realised revenue by calendar month of the order.
-- 2026-09 is partial (data stops on the 26th), which the note below the query
-- explains.
-- =============================================================================
SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'Completed'
GROUP BY month
ORDER BY month;
-- 2026-09 contains only 26 days of data, so it is a partial month. Compare
-- complete months with complete months; see 11_advanced_analysis.sql for the
-- trend measured on complete months only.


-- =============================================================================
-- Q9. What is the average order value?
-- Metric: realised revenue / number of Completed orders.
-- =============================================================================
SELECT ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100))
             / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'Completed';


-- =============================================================================
-- Q10. What percentage of orders are cancelled?
-- =============================================================================
SELECT ROUND(100 * SUM(status = 'Cancelled') / COUNT(*), 2) AS cancellation_rate_pct,
       SUM(status = 'Cancelled')                            AS cancelled_orders,
       COUNT(*)                                             AS total_orders
FROM orders;


-- =============================================================================
-- Q11. What percentage of orders are returned?
-- =============================================================================
SELECT ROUND(100 * SUM(status = 'Returned') / COUNT(*), 2) AS return_rate_pct,
       SUM(status = 'Returned')                            AS returned_orders,
       COUNT(*)                                            AS total_orders
FROM orders;


-- =============================================================================
-- Q12. Which categories have the highest profit margins?
-- Metric: realised profit / realised revenue * 100.
-- =============================================================================
SELECT pr.category,
       ROUND(100 * (SUM(oi.quantity * oi.unit_price
                        * (1 - oi.discount_percent / 100))
                    - SUM(oi.quantity * pr.cost))
             / NULLIF(SUM(oi.quantity * oi.unit_price
                          * (1 - oi.discount_percent / 100)), 0), 2) AS margin_pct
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.category
ORDER BY margin_pct DESC;


-- =============================================================================
-- Q13. Which payment methods are most commonly used?
-- Metric: share of payment records. One payment record exists per order.
-- =============================================================================
SELECT payment_method,
       COUNT(*)                                  AS payments,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM payments), 2) AS pct_of_payments
FROM payments
GROUP BY payment_method
ORDER BY payments DESC;


-- =============================================================================
-- Q14. Which payment methods have the highest failure rate?
-- Metric: payment_status = 'Failed' as a share of that method's payments.
-- =============================================================================
SELECT payment_method,
       COUNT(*)                                       AS payments,
       SUM(payment_status = 'Failed')                 AS failed_payments,
       ROUND(100 * SUM(payment_status = 'Failed') / COUNT(*), 2) AS failure_rate_pct
FROM payments
GROUP BY payment_method
ORDER BY failure_rate_pct DESC;


-- =============================================================================
-- Q15. How much potential order value is associated with failed orders?
--
-- "Failed" is ambiguous, so BOTH readings are measured and shown:
--   (a) payment failure : payments.payment_status = 'Failed'
--   (b) failed order    : order status is Cancelled or Returned, i.e. the order
--                         did not complete. This is the definition Phase 2 used.
-- In both cases the value is measured GROSS, because it is value that was
-- attempted, not value that was earned.
-- =============================================================================
-- (a) orders whose payment failed.
--     CARDINALITY: order_items is collapsed to ONE row per order before it is
--     joined to the failed-payment list, so each order's value is counted once.
WITH failed_payment AS (
    SELECT p.order_id
    FROM payments p
    WHERE p.payment_status = 'Failed'
),
order_value AS (
    SELECT oi.order_id,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS order_gross_value
    FROM order_items oi
    GROUP BY oi.order_id
)
SELECT 'payment failed' AS definition,
       COUNT(*)                                        AS orders,
       ROUND(SUM(ov.order_gross_value), 2)             AS gross_value,
       ROUND(100 * SUM(ov.order_gross_value)
             / (SELECT SUM(oi2.quantity * oi2.unit_price
                           * (1 - oi2.discount_percent / 100))
                FROM order_items oi2), 2)              AS pct_of_gross_revenue
FROM failed_payment f
JOIN order_value ov ON ov.order_id = f.order_id;

-- (b) orders that did not complete (Cancelled or Returned).
--     Same order-level-first pattern; this is a single-number answer, so there
--     is no reason to carry line grain into the final join.
WITH order_value AS (
    SELECT oi.order_id,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS order_gross_value
    FROM order_items oi
    GROUP BY oi.order_id
)
SELECT 'order did not complete' AS definition,
       COUNT(*)                                       AS orders,
       ROUND(SUM(ov.order_gross_value), 2)            AS gross_value,
       ROUND(100 * SUM(ov.order_gross_value)
             / (SELECT SUM(oi2.quantity * oi2.unit_price
                           * (1 - oi2.discount_percent / 100))
                FROM order_items oi2), 2)             AS pct_of_gross_revenue
FROM orders o
JOIN order_value ov ON ov.order_id = o.order_id
WHERE o.status IN ('Cancelled', 'Returned');

-- (c) where that lost value sits, by category.
-- The loss rate is lost / (lost + completed) for that category. Pending orders
-- are excluded from BOTH sides because their outcome is not known yet; counting
-- them would understate the rate. This is the definition Phase 2 used.
SELECT pr.category,
       COUNT(DISTINCT CASE WHEN o.status IN ('Cancelled', 'Returned')
                           THEN o.order_id END)               AS failed_orders,
       ROUND(100 * SUM(CASE WHEN o.status IN ('Cancelled', 'Returned')
                            THEN oi.quantity * oi.unit_price
                                 * (1 - oi.discount_percent / 100)
                            ELSE 0 END)
             / NULLIF(SUM(CASE WHEN o.status IN ('Cancelled', 'Returned', 'Completed')
                               THEN oi.quantity * oi.unit_price
                                    * (1 - oi.discount_percent / 100)
                               ELSE 0 END), 0), 2)            AS loss_rate_pct,
       ROUND(SUM(CASE WHEN o.status IN ('Cancelled', 'Returned')
                      THEN oi.quantity * oi.unit_price
                           * (1 - oi.discount_percent / 100)
                      ELSE 0 END), 2)                          AS lost_gross_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products pr    ON pr.product_id = oi.product_id
GROUP BY pr.category
ORDER BY lost_gross_value DESC;


-- =============================================================================
-- Q16. How does discount level relate to revenue, quantity and profit?
-- Metric: realised revenue, units and margin per discount band.
-- This describes the data. It does NOT prove the discount caused the result.
-- =============================================================================
WITH banded AS (
    SELECT CASE
               WHEN oi.discount_percent = 0                THEN '1. 0%'
               WHEN oi.discount_percent BETWEEN 1  AND 5   THEN '2. 1-5%'
               WHEN oi.discount_percent BETWEEN 6  AND 10  THEN '3. 6-10%'
               WHEN oi.discount_percent BETWEEN 11 AND 15  THEN '4. 11-15%'
               WHEN oi.discount_percent BETWEEN 16 AND 20  THEN '5. 16-20%'
               WHEN oi.discount_percent BETWEEN 21 AND 25  THEN '6. 21-25%'
               ELSE '7. 26-30%'
           END AS discount_band,
           oi.quantity, oi.unit_price, oi.discount_percent, pr.cost
    FROM order_items oi
    JOIN products pr ON pr.product_id = oi.product_id
    JOIN orders o    ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
)
SELECT discount_band,
       COUNT(*)                                      AS line_count,
       SUM(quantity)                                 AS units,
       ROUND(AVG(quantity), 2)                       AS avg_units_per_line,
       ROUND(SUM(quantity * unit_price
                 * (1 - discount_percent / 100)), 2) AS realised_revenue,
       ROUND(SUM(quantity * unit_price
                 * (1 - discount_percent / 100))
             / COUNT(*), 2)                          AS revenue_per_line,
       ROUND(100 * (SUM(quantity * unit_price
                        * (1 - discount_percent / 100))
                    - SUM(quantity * cost))
             / NULLIF(SUM(quantity * unit_price
                          * (1 - discount_percent / 100)), 0), 2) AS margin_pct
FROM banded
GROUP BY discount_band
ORDER BY discount_band;


-- =============================================================================
-- Q17. Which customers have placed the most orders?
-- Metric: COUNT of orders, any status.
-- =============================================================================
SELECT c.customer_id,
       c.name,
       c.city,
       COUNT(*) AS orders_placed
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name, c.city
ORDER BY orders_placed DESC
LIMIT 10;


-- =============================================================================
-- Q18. Which products have high revenue but low margin?
-- Definition: revenue in the top half of all products AND margin in the bottom
-- half. Percentile ranks are used instead of hand-picked cut-offs.
-- =============================================================================
WITH perf AS (
    SELECT pr.product_id,
           pr.product_name,
           pr.category,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100))       AS revenue,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100))
               - SUM(oi.quantity * pr.cost)             AS profit
    FROM order_items oi
    JOIN products pr ON pr.product_id = oi.product_id
    JOIN orders o    ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY pr.product_id, pr.product_name, pr.category
),
scored AS (
    SELECT product_name,
           category,
           revenue,
           profit,
           ROUND(100 * profit / NULLIF(revenue, 0), 2) AS margin_pct,
           PERCENT_RANK() OVER (ORDER BY revenue)      AS revenue_rank,
           PERCENT_RANK() OVER (ORDER BY profit / NULLIF(revenue, 0))
                                                       AS margin_rank
    FROM perf
)
SELECT product_name, category,
       ROUND(revenue, 2) AS realised_revenue,
       margin_pct
FROM scored
WHERE revenue_rank >= 0.5 AND margin_rank <= 0.5
ORDER BY revenue DESC
LIMIT 10;


-- =============================================================================
-- Q19. Which products have high margin but relatively low sales volume?
-- Definition: margin in the top half AND completed units in the bottom half.
-- =============================================================================
WITH perf AS (
    SELECT pr.product_id,
           pr.product_name,
           pr.category,
           SUM(oi.quantity)                                 AS units,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100))           AS revenue,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100))
               - SUM(oi.quantity * pr.cost)                 AS profit
    FROM order_items oi
    JOIN products pr ON pr.product_id = oi.product_id
    JOIN orders o    ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY pr.product_id, pr.product_name, pr.category
),
scored AS (
    SELECT product_name,
           category,
           units,
           revenue,
           ROUND(100 * profit / NULLIF(revenue, 0), 2)      AS margin_pct,
           PERCENT_RANK() OVER (ORDER BY units)             AS units_rank,
           PERCENT_RANK() OVER (ORDER BY profit / NULLIF(revenue, 0))
                                                            AS margin_rank
    FROM perf
)
SELECT product_name, category, units AS completed_units,
       ROUND(revenue, 2) AS realised_revenue, margin_pct
FROM scored
WHERE margin_rank >= 0.5 AND units_rank <= 0.5
ORDER BY margin_pct DESC
LIMIT 10;


-- =============================================================================
-- Q20. What percentage of total realised revenue comes from the top 10 customers?
-- =============================================================================
WITH per_customer AS (
    SELECT o.customer_id,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS realised_spend
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'Completed'
    GROUP BY o.customer_id
),
ranked AS (
    SELECT customer_id,
           realised_spend,
           ROW_NUMBER() OVER (ORDER BY realised_spend DESC) AS spend_rank
    FROM per_customer
)
SELECT ROUND(SUM(CASE WHEN spend_rank <= 10 THEN realised_spend ELSE 0 END), 2)
           AS top10_customer_revenue,
       ROUND(SUM(realised_spend), 2) AS total_realised_revenue,
       ROUND(100 * SUM(CASE WHEN spend_rank <= 10 THEN realised_spend ELSE 0 END)
             / SUM(realised_spend), 2) AS top10_share_pct
FROM ranked;
