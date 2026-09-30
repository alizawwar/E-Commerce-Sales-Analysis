-- =============================================================================
-- 13_phase2_reconciliation.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : reconciling SQL against Phase 2
--
-- Phase 2 (the pandas notebook) published a set of headline numbers. This file
-- recomputes each one independently in SQL and puts the two side by side.
--
-- HOW TO READ IT
--   sql_value     - computed live, right now, from the imported tables
--   phase2_value  - the number published by the Phase 2 notebook. These are
--                   carried over deliberately so the two can be compared; they
--                   are reference values, not results produced by this query.
--   tolerance     - how much difference is still "the same number" given the
--                   rounding Phase 2 used when it reported the figure
--   difference    - sql_value - phase2_value
--   status        - 'match' when the difference is inside the tolerance,
--                   otherwise 'CHECK' so it stands out immediately
--
-- A 'CHECK' row is not automatically an error. It means the two definitions
-- need to be compared, which is exactly the work this file exists to do.
-- =============================================================================

USE ecommerce_sales_analysis;


-- =============================================================================
-- PART 1 - headline metrics
-- =============================================================================
WITH metrics AS (
    SELECT 'Total orders' AS metric,
           (SELECT COUNT(*) FROM orders) AS sql_value,
           12000 AS phase2_value, 0 AS tolerance,
           'exact row count' AS note
    UNION ALL
    SELECT 'Registered customers',
           (SELECT COUNT(*) FROM customers), 1500, 0, 'exact row count'
    UNION ALL
    SELECT 'Active customers (placed >= 1 order)',
           (SELECT COUNT(DISTINCT customer_id) FROM orders), 1440, 0, 'distinct customers in orders'
    UNION ALL
    SELECT 'Inactive customers (never ordered)',
           (SELECT COUNT(*) FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.customer_id
            WHERE o.order_id IS NULL), 60, 0, 'customers with no order'
    UNION ALL
    SELECT 'Products',
           (SELECT COUNT(*) FROM products), 300, 0, 'exact row count'
    UNION ALL
    SELECT 'Order lines',
           (SELECT COUNT(*) FROM order_items), 30006, 0, 'exact row count'
    UNION ALL
    SELECT 'Payments',
           (SELECT COUNT(*) FROM payments), 12000, 0, 'one payment per order'
    UNION ALL
    SELECT 'Units, all orders',
           (SELECT SUM(quantity) FROM order_items), 50694, 0, 'SUM(quantity)'
    UNION ALL
    SELECT 'Units, completed orders',
           (SELECT SUM(oi.quantity) FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'), 38406, 0, 'completed units only'
    UNION ALL
    SELECT 'Gross revenue (PKR)',
           (SELECT SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100))
            FROM order_items oi), 845400583, 1, 'Phase 2 rounded to nearest PKR'
    UNION ALL
    SELECT 'Realised revenue (PKR)',
           (SELECT SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100))
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'), 632578306, 1, 'Phase 2 rounded to nearest PKR'
    UNION ALL
    SELECT 'Realised profit (PKR)',
           (SELECT SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100)
                       - oi.quantity * pr.cost)
            FROM order_items oi
            JOIN orders o    ON o.order_id = oi.order_id
            JOIN products pr ON pr.product_id = oi.product_id
            WHERE o.status = 'Completed'), 196295406, 1, 'Phase 2 rounded to nearest PKR'
    UNION ALL
    SELECT 'Overall margin (%)',
           (SELECT 100 * SUM(oi.quantity * oi.unit_price
                             * (1 - oi.discount_percent / 100)
                             - oi.quantity * pr.cost)
                   / SUM(oi.quantity * oi.unit_price
                         * (1 - oi.discount_percent / 100))
            FROM order_items oi
            JOIN orders o    ON o.order_id = oi.order_id
            JOIN products pr ON pr.product_id = oi.product_id
            WHERE o.status = 'Completed'), 31.03, 0.01, 'profit / revenue'
    UNION ALL
    SELECT 'Average order value (PKR)',
           (SELECT SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100))
                   / COUNT(DISTINCT o.order_id)
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'), 69698, 1, 'realised revenue / completed orders'
    UNION ALL
    SELECT 'Profit per completed order (PKR)',
           (SELECT SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100)
                       - oi.quantity * pr.cost)
                   / COUNT(DISTINCT o.order_id)
            FROM order_items oi
            JOIN orders o    ON o.order_id = oi.order_id
            JOIN products pr ON pr.product_id = oi.product_id
            WHERE o.status = 'Completed'), 21628, 1, 'realised profit / completed orders'
    UNION ALL
    SELECT 'Units per order',
           (SELECT SUM(quantity) / (SELECT COUNT(*) FROM orders)
            FROM order_items), 4.22, 0.01, 'total units / total orders'
    UNION ALL
    SELECT 'Lines per order',
           (SELECT COUNT(*) / (SELECT COUNT(*) FROM orders)
            FROM order_items), 2.50, 0.01, 'total lines / total orders'
    UNION ALL
    SELECT 'Cancellation rate (%)',
           (SELECT 100 * SUM(status = 'Cancelled') / COUNT(*) FROM orders),
           6.45, 0.01, 'cancelled / total'
    UNION ALL
    SELECT 'Return rate (%)',
           (SELECT 100 * SUM(status = 'Returned') / COUNT(*) FROM orders),
           7.75, 0.01, 'returned / total'
    UNION ALL
    SELECT 'Pending rate (%)',
           (SELECT 100 * SUM(status = 'Pending') / COUNT(*) FROM orders),
           10.17, 0.01, 'pending / total'
    UNION ALL
    SELECT 'Completion rate (%)',
           (SELECT 100 * SUM(status = 'Completed') / COUNT(*) FROM orders),
           75.63, 0.01, 'completed / total'
    UNION ALL
    SELECT 'Repeat customer rate (%)',
           (SELECT 100 * SUM(orders_placed > 1) / COUNT(*)
            FROM (SELECT COUNT(*) AS orders_placed
                  FROM orders GROUP BY customer_id) per_customer),
           90.83, 0.01, 'repeat / active customers'
    UNION ALL
    SELECT 'Repeat share of orders (%)',
           (SELECT 100 * SUM(CASE WHEN pc.orders_placed > 1 THEN 1 ELSE 0 END)
                   / COUNT(*)
            FROM orders o
            JOIN (SELECT customer_id, COUNT(*) AS orders_placed
                  FROM orders GROUP BY customer_id) pc
              ON pc.customer_id = o.customer_id),
           98.90, 0.01, 'orders placed by repeat buyers'
    UNION ALL
    SELECT 'Discounted line share (%)',
           (SELECT 100 * SUM(discount_percent > 0) / COUNT(*) FROM order_items),
           51.5, 0.1, 'Phase 2 reported to 1 dp'
    UNION ALL
    SELECT 'Average discount when discounted (%)',
           (SELECT AVG(discount_percent) FROM order_items WHERE discount_percent > 0),
           12.17, 0.01, 'mean of non-zero discounts'
    UNION ALL
    SELECT 'Discount given away, completed orders (PKR)',
           (SELECT SUM(oi.quantity * oi.unit_price
                       * (oi.discount_percent / 100))
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'), 44306903, 1, 'Phase 2 rounded to nearest PKR'
    UNION ALL
    SELECT 'Karachi realised revenue (PKR)',
           (SELECT SUM(oi.quantity * oi.unit_price
                       * (1 - oi.discount_percent / 100))
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.status = 'Completed' AND o.shipping_city = 'Karachi'),
           123442174, 1, 'top city by realised revenue'
    UNION ALL
    SELECT 'Top 10 customers share of realised revenue (%)',
           (SELECT 100 * SUM(CASE WHEN rn <= 10 THEN spend ELSE 0 END) / SUM(spend)
            FROM (SELECT SUM(oi.quantity * oi.unit_price
                             * (1 - oi.discount_percent / 100)) AS spend,
                         ROW_NUMBER() OVER (
                             ORDER BY SUM(oi.quantity * oi.unit_price
                                          * (1 - oi.discount_percent / 100)) DESC) AS rn
                  FROM orders o
                  JOIN order_items oi ON oi.order_id = o.order_id
                  WHERE o.status = 'Completed'
                  GROUP BY o.customer_id) ranked),
           3.60, 0.01, 'concentration of realised revenue'
    UNION ALL
    SELECT 'Failed orders (cancelled + returned) % of gross revenue',
           (SELECT 100 * SUM(CASE WHEN o.status IN ('Cancelled', 'Returned')
                                  THEN oi.quantity * oi.unit_price
                                       * (1 - oi.discount_percent / 100)
                                  ELSE 0 END)
                   / SUM(oi.quantity * oi.unit_price
                         * (1 - oi.discount_percent / 100))
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id),
           15.15, 0.01, 'value that did not complete, gross'
    UNION ALL
    SELECT 'Home Appliances loss rate (%)',
           (SELECT 100 * SUM(CASE WHEN o.status IN ('Cancelled', 'Returned')
                                  THEN oi.quantity * oi.unit_price
                                       * (1 - oi.discount_percent / 100)
                                  ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN o.status IN ('Cancelled', 'Returned', 'Completed')
                                     THEN oi.quantity * oi.unit_price
                                          * (1 - oi.discount_percent / 100)
                                     ELSE 0 END), 0)
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            JOIN products pr    ON pr.product_id = oi.product_id
            WHERE pr.category = 'Home Appliances'),
           18.75, 0.01, 'lost / (lost + completed), worst category'
    UNION ALL
    SELECT 'First 6 complete months average revenue (PKR)',
           (SELECT AVG(revenue)
            FROM (SELECT month, revenue,
                         ROW_NUMBER() OVER (ORDER BY month) AS m,
                         COUNT(*) OVER () AS n
                  FROM (SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
                               SUM(oi.quantity * oi.unit_price
                                   * (1 - oi.discount_percent / 100)) AS revenue
                        FROM orders o
                        JOIN order_items oi ON oi.order_id = o.order_id
                        WHERE o.status = 'Completed'
                          AND o.order_date < '2026-09-01'
                        GROUP BY month) monthly) numbered
            WHERE m <= 6),
           22850000, 10000, 'Phase 2 quoted 22.85M (rounded to millions)'
    UNION ALL
    SELECT 'Last 6 complete months average revenue (PKR)',
           (SELECT AVG(revenue)
            FROM (SELECT month, revenue,
                         ROW_NUMBER() OVER (ORDER BY month) AS m,
                         COUNT(*) OVER () AS n
                  FROM (SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
                               SUM(oi.quantity * oi.unit_price
                                   * (1 - oi.discount_percent / 100)) AS revenue
                        FROM orders o
                        JOIN order_items oi ON oi.order_id = o.order_id
                        WHERE o.status = 'Completed'
                          AND o.order_date < '2026-09-01'
                        GROUP BY month) monthly) numbered
            WHERE m > n - 6),
           28210000, 10000, 'Phase 2 quoted 28.21M (rounded to millions)'
    UNION ALL
    SELECT 'Last 6 vs first 6 complete months change (%)',
           (SELECT 100 * (
                (SELECT AVG(revenue)
                 FROM (SELECT revenue,
                              ROW_NUMBER() OVER (ORDER BY month) AS m,
                              COUNT(*) OVER () AS n
                       FROM (SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
                                    SUM(oi.quantity * oi.unit_price
                                        * (1 - oi.discount_percent / 100)) AS revenue
                             FROM orders o
                             JOIN order_items oi ON oi.order_id = o.order_id
                             WHERE o.status = 'Completed'
                               AND o.order_date < '2026-09-01'
                             GROUP BY month) monthly) numbered
                 WHERE m > n - 6)
                /
                (SELECT AVG(revenue)
                 FROM (SELECT revenue,
                              ROW_NUMBER() OVER (ORDER BY month) AS m
                       FROM (SELECT DATE_FORMAT(o.order_date, '%Y-%m') AS month,
                                    SUM(oi.quantity * oi.unit_price
                                        * (1 - oi.discount_percent / 100)) AS revenue
                             FROM orders o
                             JOIN order_items oi ON oi.order_id = o.order_id
                             WHERE o.status = 'Completed'
                               AND o.order_date < '2026-09-01'
                             GROUP BY month) monthly) numbered
                 WHERE m <= 6)
                - 1)),
           23.5, 0.1, 'growth of complete months only'
)
SELECT metric,
       ROUND(sql_value, 2)                                       AS sql_value,
       ROUND(phase2_value, 2)                                    AS phase2_value,
       ROUND(sql_value - phase2_value, 2)                        AS difference,
       ROUND(tolerance, 2)                                       AS tolerance,
       CASE WHEN ABS(sql_value - phase2_value) <= tolerance
            THEN 'match' ELSE 'CHECK' END                        AS status,
       note
FROM metrics
ORDER BY status DESC, metric;


-- =============================================================================
-- PART 2 - category revenue, all ten categories
-- =============================================================================
WITH phase2_categories AS (
    SELECT 'Electronics'        AS category, 177321319 AS phase2_revenue
    UNION ALL SELECT 'Home Appliances',    158512078
    UNION ALL SELECT 'Computers',          153812524
    UNION ALL SELECT 'Home & Kitchen',      42028660
    UNION ALL SELECT 'Fashion',             26808740
    UNION ALL SELECT 'Mobile Accessories',  21893346
    UNION ALL SELECT 'Sports',              18580378
    UNION ALL SELECT 'Beauty',              18449332
    UNION ALL SELECT 'Books',                7878237
    UNION ALL SELECT 'Grocery',              7293693
),
sql_categories AS (
    SELECT pr.category,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS revenue
    FROM order_items oi
    JOIN products pr ON pr.product_id = oi.product_id
    JOIN orders o    ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY pr.category
)
SELECT p2.category,
       ROUND(s.revenue, 2)                                  AS sql_revenue,
       p2.phase2_revenue,
       ROUND(s.revenue - p2.phase2_revenue, 2)              AS difference,
       CASE WHEN ABS(s.revenue - p2.phase2_revenue) <= 1
            THEN 'match' ELSE 'CHECK' END                   AS status
FROM phase2_categories p2
LEFT JOIN sql_categories s ON s.category = p2.category
ORDER BY p2.phase2_revenue DESC;
