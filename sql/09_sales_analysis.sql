-- =============================================================================
-- 09_sales_analysis.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : sales analysis and discount analysis
--
-- DEFINITIONS USED IN THIS FILE
--   total orders     : every row in `orders`
--   completed orders : orders with status = 'Completed'
--   completion rate  : completed / total
--   cancellation rate: Cancelled / total
--   return rate      : Returned / total
--   pending rate     : Pending / total
--   realised revenue : revenue from Completed orders only
--   AOV              : realised revenue / completed orders
--   lines per order  : COUNT(order_items) / COUNT(orders)
--   units per order  : SUM(quantity) / COUNT(orders)
--
-- The dataset window runs from 2024-10-01 to 2026-09-26, so 2026-09 is a PARTIAL
-- month and must not be compared with full months. It is kept in the output and
-- labelled rather than hidden.
-- =============================================================================

USE ecommerce_sales_analysis;


-- =============================================================================
-- 1. Total orders
-- =============================================================================
SELECT COUNT(*) AS total_orders
FROM orders;


-- =============================================================================
-- 2. Orders by status, with every rate in a single row
-- =============================================================================
SELECT COUNT(*)                                          AS total_orders,
       SUM(status = 'Completed')                         AS completed_orders,
       SUM(status = 'Cancelled')                         AS cancelled_orders,
       SUM(status = 'Returned')                          AS returned_orders,
       SUM(status = 'Pending')                           AS pending_orders,
       ROUND(100 * SUM(status = 'Completed') / COUNT(*), 2) AS completion_rate_pct,
       ROUND(100 * SUM(status = 'Cancelled') / COUNT(*), 2) AS cancellation_rate_pct,
       ROUND(100 * SUM(status = 'Returned')  / COUNT(*), 2) AS return_rate_pct,
       ROUND(100 * SUM(status = 'Pending')   / COUNT(*), 2) AS pending_rate_pct
FROM orders;


-- =============================================================================
-- 3. Monthly order volume
-- =============================================================================
SELECT DATE_FORMAT(order_date, '%Y-%m')       AS month,
       COUNT(*)                               AS orders,
       SUM(status = 'Completed')              AS completed_orders,
       SUM(status = 'Cancelled')              AS cancelled_orders,
       SUM(status = 'Returned')               AS returned_orders,
       SUM(status = 'Pending')                AS pending_orders
FROM orders
GROUP BY month
ORDER BY month;


-- =============================================================================
-- 4. Monthly realised revenue and profit, with AOV
-- =============================================================================
-- Revenue and profit are attached to the order DATE and counted only when the
-- order completed. AOV divides by the completed orders in that month.
WITH monthly AS (
    SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
           COUNT(DISTINCT CASE WHEN o.status = 'Completed' THEN o.order_id END)
                                                 AS completed_orders,
           SUM(CASE WHEN o.status = 'Completed' THEN oi.quantity ELSE 0 END)
                                                 AS completed_units,
           SUM(CASE WHEN o.status = 'Completed'
                    THEN oi.quantity * oi.unit_price
                         * (1 - oi.discount_percent / 100) ELSE 0 END)
                                                 AS realised_revenue,
           SUM(CASE WHEN o.status = 'Completed'
                    THEN oi.quantity * oi.unit_price
                         * (1 - oi.discount_percent / 100)
                         - oi.quantity * pr.cost ELSE 0 END)
                                                 AS realised_profit
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    JOIN products pr    ON pr.product_id = oi.product_id
    GROUP BY month
)
SELECT month,
       completed_orders,
       completed_units,
       ROUND(realised_revenue, 2)                                   AS realised_revenue,
       ROUND(realised_profit, 2)                                    AS realised_profit,
       ROUND(realised_revenue / NULLIF(completed_orders, 0), 2)     AS avg_order_value,
       ROUND(100 * realised_profit / NULLIF(realised_revenue, 0), 2) AS margin_pct,
       CASE WHEN month = '2026-09' THEN 'partial month' ELSE '' END AS note
FROM monthly
ORDER BY month;


-- =============================================================================
-- 5. Yearly realised revenue and profit
-- =============================================================================
WITH yearly AS (
    SELECT YEAR(o.order_date) AS year,
           COUNT(DISTINCT CASE WHEN o.status = 'Completed' THEN o.order_id END)
                              AS completed_orders,
           SUM(CASE WHEN o.status = 'Completed'
                    THEN oi.quantity * oi.unit_price
                         * (1 - oi.discount_percent / 100) ELSE 0 END)
                              AS realised_revenue,
           SUM(CASE WHEN o.status = 'Completed'
                    THEN oi.quantity * oi.unit_price
                         * (1 - oi.discount_percent / 100)
                         - oi.quantity * pr.cost ELSE 0 END)
                              AS realised_profit
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    JOIN products pr    ON pr.product_id = oi.product_id
    GROUP BY year
)
SELECT year,
       completed_orders,
       ROUND(realised_revenue, 2)                               AS realised_revenue,
       ROUND(realised_profit, 2)                                AS realised_profit,
       ROUND(100 * realised_profit / NULLIF(realised_revenue, 0), 2) AS margin_pct
FROM yearly
ORDER BY year;
-- 2026 is a partial year: it stops on 2026-09-26.


-- =============================================================================
-- 6. Average order value  (headline, whole dataset)
-- =============================================================================
SELECT ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100))
             / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'Completed';


-- =============================================================================
-- 7. Average lines per order and average units per order
-- =============================================================================
-- Lines per order is about the basket shape (how many different products),
-- units per order is about its size (how many physical items). They are often
-- quoted interchangeably and they are not the same thing.
SELECT COUNT(*)                          AS total_orders,
       (SELECT COUNT(*) FROM order_items) AS total_lines,
       (SELECT SUM(quantity) FROM order_items) AS total_units,
       ROUND((SELECT COUNT(*) FROM order_items) / COUNT(*), 2) AS avg_lines_per_order,
       ROUND((SELECT SUM(quantity) FROM order_items) / COUNT(*), 2) AS avg_units_per_order
FROM orders;


-- =============================================================================
-- 8. Units sold  (all orders versus completed orders)
-- =============================================================================
SELECT SUM(oi.quantity)                                        AS units_all_orders,
       SUM(CASE WHEN o.status = 'Completed' THEN oi.quantity ELSE 0 END)
                                                              AS units_completed_orders
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id;


-- =============================================================================
-- 9. Revenue by city  (realised)
-- =============================================================================
SELECT o.shipping_city,
       COUNT(DISTINCT o.order_id)                          AS completed_orders,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2)    AS realised_revenue,
       ROUND(100 * SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100))
             / (SELECT SUM(oi2.quantity * oi2.unit_price
                           * (1 - oi2.discount_percent / 100))
                FROM order_items oi2
                JOIN orders o2 ON o2.order_id = oi2.order_id
                WHERE o2.status = 'Completed'), 2)        AS pct_of_realised_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'Completed'
GROUP BY o.shipping_city
ORDER BY realised_revenue DESC;


-- =============================================================================
-- 10. Profit by city  (realised)
-- =============================================================================
SELECT o.shipping_city,
       COUNT(DISTINCT o.order_id) AS completed_orders,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)
                 - oi.quantity * pr.cost), 2)             AS realised_profit,
       ROUND(100 * SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100)
                       - oi.quantity * pr.cost)
             / NULLIF(SUM(oi.quantity * oi.unit_price
                          * (1 - oi.discount_percent / 100)), 0), 2) AS margin_pct
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products pr    ON pr.product_id = oi.product_id
WHERE o.status = 'Completed'
GROUP BY o.shipping_city
ORDER BY realised_profit DESC;


-- =============================================================================
-- 11. Revenue by category  (realised)
-- =============================================================================
SELECT pr.category,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2)    AS realised_revenue
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.category
ORDER BY realised_revenue DESC;


-- =============================================================================
-- 12. Profit by category  (realised)
-- =============================================================================
SELECT pr.category,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)
                 - oi.quantity * pr.cost), 2)             AS realised_profit,
       ROUND(100 * SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100)
                       - oi.quantity * pr.cost)
             / NULLIF(SUM(oi.quantity * oi.unit_price
                          * (1 - oi.discount_percent / 100)), 0), 2) AS margin_pct
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.category
ORDER BY realised_profit DESC;


-- =============================================================================
-- 13. DISCOUNT ANALYSIS - the headline numbers
-- =============================================================================
-- The dataset only ever uses 0, 5, 10, 15, 20, 25 and 30 percent, so the bands
-- used below line up exactly with real values.
SELECT COUNT(*)                                        AS total_lines,
       SUM(discount_percent > 0)                       AS discounted_lines,
       ROUND(100 * SUM(discount_percent > 0) / COUNT(*), 2) AS discounted_line_pct,
       ROUND(AVG(CASE WHEN discount_percent > 0
                      THEN discount_percent END), 2)   AS avg_discount_pct_when_discounted,
       ROUND(AVG(discount_percent), 2)                 AS avg_discount_pct_all_lines
FROM order_items;

-- Total discount given away, on completed orders, in money.
-- (unit_price is the pre-discount price, so the giveaway is quantity * unit_price
--  * discount%, which is exactly the difference between gross and realised.)
SELECT ROUND(SUM(oi.quantity * oi.unit_price
                 * (oi.discount_percent / 100)), 2)    AS discount_given_away_completed
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status = 'Completed';


-- =============================================================================
-- 14-16. Revenue, units and margin by discount band  (realised)
-- =============================================================================
-- The CASE is written once in the CTE so the three measures are guaranteed to
-- use identical bands.
WITH banded AS (
    SELECT CASE
               WHEN oi.discount_percent = 0                    THEN '1. 0%'
               WHEN oi.discount_percent BETWEEN 1  AND 5      THEN '2. 1-5%'
               WHEN oi.discount_percent BETWEEN 6  AND 10     THEN '3. 6-10%'
               WHEN oi.discount_percent BETWEEN 11 AND 15     THEN '4. 11-15%'
               WHEN oi.discount_percent BETWEEN 16 AND 20     THEN '5. 16-20%'
               WHEN oi.discount_percent BETWEEN 21 AND 25     THEN '6. 21-25%'
               ELSE '7. 26-30%'
           END AS discount_band,
           oi.quantity,
           oi.unit_price,
           oi.discount_percent,
           pr.cost
    FROM order_items oi
    JOIN products pr ON pr.product_id = oi.product_id
    JOIN orders o    ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
)
SELECT discount_band,
       COUNT(*)                                        AS line_count,
       ROUND(100 * COUNT(*)
             / SUM(COUNT(*)) OVER (), 2)              AS pct_of_lines,
       SUM(quantity)                                   AS units,
       ROUND(AVG(quantity), 2)                         AS units_per_line,
       ROUND(SUM(quantity * unit_price
                 * (1 - discount_percent / 100)), 2)   AS realised_revenue,
       ROUND(SUM(quantity * unit_price
                 * (1 - discount_percent / 100))
             / COUNT(*), 2)                            AS revenue_per_line,
       ROUND(SUM(quantity * unit_price
                 * (1 - discount_percent / 100))
             - SUM(quantity * cost), 2)                AS realised_profit,
       ROUND(100 * (SUM(quantity * unit_price
                        * (1 - discount_percent / 100))
                    - SUM(quantity * cost))
             / NULLIF(SUM(quantity * unit_price
                          * (1 - discount_percent / 100)), 0), 2) AS margin_pct
FROM banded
GROUP BY discount_band
ORDER BY discount_band;

-- NOTE ON INTERPRETATION
--   This table shows how revenue, units and margin DIFFER between discount
--   bands. It does not show that the discount caused the difference. Product
--   mix, order size and which items were put on promotion all move at the same
--   time, and a single observational dataset cannot separate them. The honest
--   statement is "heavily discounted lines show lower revenue per line and a
--   lower margin", not "discounts reduce revenue".
