-- =============================================================================
-- 14_headline_metrics.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : headline scorecard
--
-- One query set that returns every top-line number in the project, so the whole
-- summary can be reproduced with a single command and checked at a glance:
--
--     mysql -u root --database=ecommerce_sales_analysis < sql/14_headline_metrics.sql
--
-- Every value is computed live from the imported tables. Nothing here is copied
-- from Phase 2.
--
-- DEFINITIONS (kept identical everywhere in this project)
--   gross / potential revenue : every order line, whatever the order status
--   realised revenue          : Completed orders only
--   realised profit           : completed revenue - product cost, Completed only
--   AOV                       : realised revenue / completed orders
--
-- CARDINALITY: every monetary figure below is a scalar subquery over a single
-- table. No two child tables are joined to each other, so no result can be
-- multiplied by a one-to-many relationship.
-- =============================================================================

USE ecommerce_sales_analysis;


-- -----------------------------------------------------------------------------
-- A. One row per headline metric
-- -----------------------------------------------------------------------------
SELECT 'Total orders' AS metric,
       COUNT(*) AS metric_value
FROM orders
UNION ALL
SELECT 'Completed orders', COUNT(*) FROM orders WHERE status = 'Completed'
UNION ALL
SELECT 'Pending orders', COUNT(*) FROM orders WHERE status = 'Pending'
UNION ALL
SELECT 'Cancelled orders', COUNT(*) FROM orders WHERE status = 'Cancelled'
UNION ALL
SELECT 'Returned orders', COUNT(*) FROM orders WHERE status = 'Returned'
UNION ALL
SELECT 'Completion rate (%)',
       100 * SUM(status = 'Completed') / COUNT(*) FROM orders
UNION ALL
SELECT 'Cancellation rate (%)',
       100 * SUM(status = 'Cancelled') / COUNT(*) FROM orders
UNION ALL
SELECT 'Return rate (%)',
       100 * SUM(status = 'Returned') / COUNT(*) FROM orders
UNION ALL
SELECT 'Pending rate (%)',
       100 * SUM(status = 'Pending') / COUNT(*) FROM orders
UNION ALL
SELECT 'Registered customers', COUNT(*) FROM customers
UNION ALL
SELECT 'Active customers (ordered at least once)',
       COUNT(DISTINCT customer_id) FROM orders
UNION ALL
SELECT 'Inactive customers (never ordered)',
       COUNT(*) FROM customers c
       LEFT JOIN orders o ON o.customer_id = c.customer_id
       WHERE o.order_id IS NULL
UNION ALL
SELECT 'Repeat customer rate (%)',
       100 * SUM(orders_placed > 1) / COUNT(*)
       FROM (SELECT COUNT(*) AS orders_placed FROM orders GROUP BY customer_id) pc
UNION ALL
SELECT 'Products', COUNT(*) FROM products
UNION ALL
SELECT 'Order lines', COUNT(*) FROM order_items
UNION ALL
SELECT 'Units sold (all orders)', SUM(quantity) FROM order_items
UNION ALL
SELECT 'Units sold (completed orders)',
       SUM(oi.quantity) FROM order_items oi
       JOIN orders o ON o.order_id = oi.order_id
       WHERE o.status = 'Completed'
UNION ALL
SELECT 'Lines per order', COUNT(*) / (SELECT COUNT(*) FROM orders) FROM order_items
UNION ALL
SELECT 'Units per order', SUM(quantity) / (SELECT COUNT(*) FROM orders) FROM order_items
UNION ALL
SELECT 'Gross / potential revenue (PKR)',
       SUM(quantity * unit_price * (1 - discount_percent / 100)) FROM order_items
UNION ALL
SELECT 'Realised revenue (PKR)',
       SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100))
       FROM order_items oi
       JOIN orders o ON o.order_id = oi.order_id
       WHERE o.status = 'Completed'
UNION ALL
SELECT 'Realised profit (PKR)',
       SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100)
           - oi.quantity * pr.cost)
       FROM order_items oi
       JOIN orders o    ON o.order_id = oi.order_id
       JOIN products pr ON pr.product_id = oi.product_id
       WHERE o.status = 'Completed'
UNION ALL
SELECT 'Overall margin (%)',
       100 * SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100)
                 - oi.quantity * pr.cost)
           / SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100))
       FROM order_items oi
       JOIN orders o    ON o.order_id = oi.order_id
       JOIN products pr ON pr.product_id = oi.product_id
       WHERE o.status = 'Completed'
UNION ALL
SELECT 'Average order value (PKR)',
       SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100))
       / COUNT(DISTINCT o.order_id)
       FROM order_items oi
       JOIN orders o ON o.order_id = oi.order_id
       WHERE o.status = 'Completed'
UNION ALL
SELECT 'Profit per completed order (PKR)',
       SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100)
           - oi.quantity * pr.cost) / COUNT(DISTINCT o.order_id)
       FROM order_items oi
       JOIN orders o    ON o.order_id = oi.order_id
       JOIN products pr ON pr.product_id = oi.product_id
       WHERE o.status = 'Completed'
UNION ALL
SELECT 'Discounted line share (%)',
       100 * SUM(discount_percent > 0) / COUNT(*) FROM order_items
UNION ALL
SELECT 'Average discount when discounted (%)',
       AVG(discount_percent) FROM order_items WHERE discount_percent > 0
UNION ALL
SELECT 'Discount given away, completed orders (PKR)',
       SUM(oi.quantity * oi.unit_price * (oi.discount_percent / 100))
       FROM order_items oi
       JOIN orders o ON o.order_id = oi.order_id
       WHERE o.status = 'Completed'
UNION ALL
SELECT 'Top 10 customers share of realised revenue (%)',
       100 * SUM(CASE WHEN rn <= 10 THEN spend ELSE 0 END) / SUM(spend)
       FROM (SELECT SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100)) AS spend,
                    ROW_NUMBER() OVER (
                        ORDER BY SUM(oi.quantity * oi.unit_price
                                     * (1 - oi.discount_percent / 100)) DESC) AS rn
             FROM orders o
             JOIN order_items oi ON oi.order_id = o.order_id
             WHERE o.status = 'Completed'
             GROUP BY o.customer_id) ranked
UNION ALL
SELECT 'Failed orders (cancelled + returned) % of gross revenue',
       100 * SUM(CASE WHEN o.status IN ('Cancelled', 'Returned')
                      THEN oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100)
                      ELSE 0 END)
           / SUM(oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100))
       FROM orders o
       JOIN order_items oi ON oi.order_id = o.order_id;


-- -----------------------------------------------------------------------------
-- B. "Best of" highlights - the answers a stakeholder asks for first
-- -----------------------------------------------------------------------------
SELECT 'Top category by realised revenue' AS highlight,
       pr.category AS winner,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS metric_value
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.category
ORDER BY metric_value DESC
LIMIT 1;

SELECT 'Top product by realised revenue' AS highlight,
       pr.product_name AS winner,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS metric_value
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.product_id, pr.product_name
ORDER BY metric_value DESC
LIMIT 1;

SELECT 'Top product by units (all orders)' AS highlight,
       pr.product_name AS winner,
       SUM(oi.quantity) AS metric_value
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
GROUP BY pr.product_id, pr.product_name
ORDER BY metric_value DESC
LIMIT 1;

SELECT 'Top city by realised revenue' AS highlight,
       o.shipping_city AS winner,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS metric_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'Completed'
GROUP BY o.shipping_city
ORDER BY metric_value DESC
LIMIT 1;

SELECT 'Most used payment method' AS highlight,
       p.payment_method AS winner,
       COUNT(*) AS metric_value
FROM payments p
GROUP BY p.payment_method
ORDER BY metric_value DESC
LIMIT 1;
