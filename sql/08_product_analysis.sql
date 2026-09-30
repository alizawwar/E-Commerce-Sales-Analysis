-- =============================================================================
-- 08_product_analysis.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : product analysis
--
-- DEFINITIONS USED IN THIS FILE
--   units sold          : SUM(order_items.quantity)
--   orders containing X : COUNT(DISTINCT orders.order_id), so a product ordered
--                         twice in one order still counts as one order
--   revenue             : quantity * unit_price * (1 - discount_percent / 100)
--   cost                : quantity * products.cost
--   profit              : revenue - cost      (discount reduces revenue, not cost)
--   margin              : profit / revenue * 100
--
-- Realised figures (Completed orders only) are used for revenue, profit and
-- margin. Gross totals are shown when the question is about everything.
--
-- A note on unit_price: it is the price actually charged, and it is not the same
-- as the catalogue price in `products`. See section 9.
-- =============================================================================

USE ecommerce_sales_analysis;


-- =============================================================================
-- 1. Best-selling products by units
-- =============================================================================
-- Both bases are shown side by side, because they answer different questions:
--   units_all_orders       = demand: everything customers tried to buy
--   units_completed_orders = realised: units in orders that actually completed
-- The Phase 2 business answer quoted 1,190 units for the top product, which is
-- the completed figure. The 1,568 all-orders figure is larger and is not a
-- contradiction - it is the same data measured a different way.
SELECT pr.product_id,
       pr.product_name,
       pr.category,
       SUM(oi.quantity) AS units_all_orders,
       SUM(CASE WHEN o.status = 'Completed' THEN oi.quantity ELSE 0 END)
                        AS units_completed_orders
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
GROUP BY pr.product_id, pr.product_name, pr.category
ORDER BY units_all_orders DESC
LIMIT 10;


-- =============================================================================
-- 2. Highest revenue products  (realised)
-- =============================================================================
SELECT pr.product_id,
       pr.product_name,
       pr.category,
       SUM(oi.quantity) AS units_sold,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.product_id, pr.product_name, pr.category
ORDER BY realised_revenue DESC
LIMIT 10;


-- =============================================================================
-- 3. Most frequently ordered products
-- =============================================================================
-- "Frequency" means distinct orders that contain the product. A product with
-- 10 units across 10 orders is more broadly popular than one with 10 units in a
-- single order, and this query separates the two cases.
SELECT pr.product_id,
       pr.product_name,
       COUNT(DISTINCT oi.order_id) AS orders_containing_product,
       SUM(oi.quantity)            AS units_sold
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
GROUP BY pr.product_id, pr.product_name
ORDER BY orders_containing_product DESC
LIMIT 10;


-- =============================================================================
-- 4. Product profitability  (realised)
-- =============================================================================
SELECT pr.product_id,
       pr.product_name,
       pr.category,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue,
       ROUND(SUM(oi.quantity * pr.cost), 2)             AS realised_cost,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100))
             - SUM(oi.quantity * pr.cost), 2)           AS realised_profit
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.product_id, pr.product_name, pr.category
ORDER BY realised_profit DESC
LIMIT 10;


-- =============================================================================
-- 5. Product margins  (realised)
-- =============================================================================
-- NULLIF(...,0) prevents a divide-by-zero if any product ever had zero revenue.
-- The table is sorted by margin so the most profitable products per rupee of
-- sale appear first, not the biggest sellers.
SELECT pr.product_id,
       pr.product_name,
       pr.category,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100))
             - SUM(oi.quantity * pr.cost), 2)           AS realised_profit,
       ROUND(100 * (SUM(oi.quantity * oi.unit_price
                        * (1 - oi.discount_percent / 100))
                    - SUM(oi.quantity * pr.cost))
             / NULLIF(SUM(oi.quantity * oi.unit_price
                          * (1 - oi.discount_percent / 100)), 0), 2)
                                                        AS margin_pct
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.product_id, pr.product_name, pr.category
ORDER BY margin_pct DESC
LIMIT 10;


-- =============================================================================
-- 6. Category performance  (realised)
-- =============================================================================
SELECT pr.category,
       COUNT(DISTINCT o.order_id)                     AS completed_orders,
       SUM(oi.quantity)                               AS units_sold,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue,
       ROUND(SUM(oi.quantity * pr.cost), 2)           AS realised_cost,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100))
             - SUM(oi.quantity * pr.cost), 2)         AS realised_profit,
       ROUND(100 * (SUM(oi.quantity * oi.unit_price
                        * (1 - oi.discount_percent / 100))
                    - SUM(oi.quantity * pr.cost))
             / NULLIF(SUM(oi.quantity * oi.unit_price
                          * (1 - oi.discount_percent / 100)), 0), 2)
                                                      AS margin_pct
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.category
ORDER BY realised_revenue DESC;


-- =============================================================================
-- 7. Subcategory performance  (realised)
-- =============================================================================
SELECT pr.category,
       pr.subcategory,
       COUNT(DISTINCT o.order_id)                     AS completed_orders,
       SUM(oi.quantity)                               AS units_sold,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS realised_revenue,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100))
             - SUM(oi.quantity * pr.cost), 2)         AS realised_profit,
       ROUND(100 * (SUM(oi.quantity * oi.unit_price
                        * (1 - oi.discount_percent / 100))
                    - SUM(oi.quantity * pr.cost))
             / NULLIF(SUM(oi.quantity * oi.unit_price
                          * (1 - oi.discount_percent / 100)), 0), 2)
                                                      AS margin_pct
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
JOIN orders o    ON o.order_id = oi.order_id
WHERE o.status = 'Completed'
GROUP BY pr.category, pr.subcategory
ORDER BY realised_revenue DESC
LIMIT 15;


-- =============================================================================
-- 8. Catalogue price versus transaction price
-- =============================================================================
-- These are two different things and must never be confused:
--   products.price      = the catalogue price today
--   order_items.unit_price = what the customer actually paid on that line
-- They are not expected to be equal. This query measures how far apart they are.
SELECT COUNT(*)                                            AS line_count,
       SUM(oi.unit_price = pr.price)                       AS lines_at_catalogue_price,
       SUM(oi.unit_price <> pr.price)                      AS lines_off_catalogue_price,
       ROUND(AVG(oi.unit_price - pr.price), 2)             AS avg_difference,
       ROUND(MIN(oi.unit_price - pr.price), 2)             AS min_difference,
       ROUND(MAX(oi.unit_price - pr.price), 2)             AS max_difference
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id;


-- =============================================================================
-- 9. How much does the transaction price wander per product?
-- =============================================================================
-- Shows products with the widest spread between their cheapest and dearest
-- transaction price, and how many different prices each has been sold at.
SELECT pr.product_id,
       pr.product_name,
       pr.price                                   AS catalogue_price,
       COUNT(DISTINCT oi.unit_price)              AS distinct_prices_sold_at,
       MIN(oi.unit_price)                         AS min_unit_price,
       MAX(oi.unit_price)                         AS max_unit_price,
       ROUND(MAX(oi.unit_price) - MIN(oi.unit_price), 2) AS price_spread
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
GROUP BY pr.product_id, pr.product_name, pr.price
ORDER BY price_spread DESC
LIMIT 10;
