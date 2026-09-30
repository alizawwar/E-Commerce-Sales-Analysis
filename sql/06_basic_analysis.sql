-- =============================================================================
-- 06_basic_analysis.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : core SQL techniques on real data
--
-- This file is the "fundamentals" tour. Each query is small and shows one
-- technique, but every one of them answers something a shop owner could
-- actually ask. None of them are toy examples with made-up tables.
--
-- TECHNIQUES COVERED
--   SELECT / projection, WHERE, ORDER BY, LIMIT, DISTINCT, BETWEEN, IN, LIKE,
--   CASE, aggregate functions, GROUP BY, HAVING, column and table aliases.
--
-- REMINDER - THE REVENUE FORMULA USED THROUGHOUT THIS PROJECT
--   line revenue = quantity * unit_price * (1 - discount_percent / 100)
--   "Gross"      = every order line, whatever the order status.
--   "Realised"   = Completed orders only.
--   These two words mean the same thing in every SQL file here.
-- =============================================================================

USE ecommerce_sales_analysis;


-- =============================================================================
-- 1. SELECT  -  choose columns instead of pulling everything
-- =============================================================================
-- Business question: what does the product catalogue actually contain?
-- Only the columns that are needed are requested; `stock_quantity` and `cost`
-- are left out because this view is for browsing, not for costing.
SELECT product_id,
       product_name,
       category,
       brand,
       price
FROM products
LIMIT 5;


-- =============================================================================
-- 2. WHERE  -  filter rows
-- =============================================================================
-- Business question: how many customers are registered in Lahore?
SELECT COUNT(*) AS lahore_customers
FROM customers
WHERE city = 'Lahore';


-- =============================================================================
-- 3. ORDER BY + LIMIT  -  "show me the biggest / smallest"
-- =============================================================================
-- Business question: what are the ten most expensive products in the catalogue?
SELECT product_name,
       category,
       price
FROM products
ORDER BY price DESC
LIMIT 10;


-- =============================================================================
-- 4. DISTINCT  -  what values exist at all?
-- =============================================================================
-- Business question: which product categories does the shop sell?
SELECT DISTINCT category
FROM products
ORDER BY category;


-- =============================================================================
-- 5. BETWEEN  -  an inclusive range filter
-- =============================================================================
-- Business question: how many orders arrived in the first half of 2026?
-- BETWEEN is inclusive of both ends, so this covers 1 January to 30 June.
SELECT COUNT(*) AS orders_h1_2026
FROM orders
WHERE order_date BETWEEN '2026-01-01' AND '2026-06-30';


-- =============================================================================
-- 6. IN  -  match against a list
-- =============================================================================
-- Business question: how much order value sits in orders that did not complete?
-- Pending, Cancelled and Returned are grouped here as "not completed".
SELECT COUNT(*) AS not_completed_orders
FROM orders
WHERE status IN ('Pending', 'Cancelled', 'Returned');


-- =============================================================================
-- 7. LIKE  -  pattern matching
-- =============================================================================
-- Business question: how many customers use a Gmail address?
-- The % wildcards mean "anything before" and "anything after" @gmail.com.
SELECT COUNT(*) AS gmail_customers
FROM customers
WHERE email LIKE '%@gmail.com';


-- =============================================================================
-- 8. CASE  -  turn a value into a label
-- =============================================================================
-- Business question: how are customers spread across age bands?
-- The raw ages are 18-65; nobody wants to read 46 separate counts.
SELECT CASE
           WHEN age BETWEEN 18 AND 25 THEN '18-25'
           WHEN age BETWEEN 26 AND 35 THEN '26-35'
           WHEN age BETWEEN 36 AND 45 THEN '36-45'
           WHEN age BETWEEN 46 AND 55 THEN '46-55'
           ELSE '56-65'
       END AS age_band,
       COUNT(*) AS customers
FROM customers
GROUP BY age_band
ORDER BY age_band;


-- =============================================================================
-- 9. AGGREGATE FUNCTIONS  -  summarise a whole table into one row
-- =============================================================================
-- Business question: what does a typical order line look like?
SELECT COUNT(*)                AS line_count,
       SUM(quantity)           AS total_units,
       ROUND(AVG(quantity), 2) AS avg_units_per_line,
       MIN(unit_price)         AS cheapest_unit_price,
       MAX(unit_price)         AS dearest_unit_price,
       ROUND(AVG(unit_price), 2) AS avg_unit_price
FROM order_items;


-- =============================================================================
-- 10. GROUP BY + alias  -  one row per group
-- =============================================================================
-- Business question: how many orders are in each status?
-- The alias `orders` is reused in ORDER BY; MySQL allows that.
SELECT status,
       COUNT(*) AS order_count
FROM orders
GROUP BY status
ORDER BY order_count DESC;


-- =============================================================================
-- 11. GROUP BY + HAVING  -  filter the groups, not the rows
-- =============================================================================
-- Business question: which shipping cities handled more than 800 orders?
-- WHERE filters rows before grouping; HAVING filters groups after aggregating.
SELECT shipping_city,
       COUNT(*) AS order_count
FROM orders
GROUP BY shipping_city
HAVING COUNT(*) > 800
ORDER BY order_count DESC;


-- =============================================================================
-- 12. Aliases  -  name a calculated column
-- =============================================================================
-- Business question: what is the gross revenue of each category?
-- `list_price` is used for the catalogue side so it is never confused with the
-- transaction price in order_items.
SELECT pr.category,
       ROUND(SUM(oi.quantity * oi.unit_price
                 * (1 - oi.discount_percent / 100)), 2) AS gross_revenue
FROM order_items oi
JOIN products pr ON pr.product_id = oi.product_id
GROUP BY pr.category
ORDER BY gross_revenue DESC;


-- =============================================================================
-- 13. COUNT(DISTINCT ...)  -  how many different things?
-- =============================================================================
-- Business question: how many different customers have ever placed an order?
SELECT COUNT(DISTINCT customer_id) AS customers_who_ordered,
       COUNT(*)                    AS total_orders
FROM orders;


-- =============================================================================
-- 14. Combining techniques  -  the shape most analysis queries take
-- =============================================================================
-- Business question: which five brands appear in the most expensive half of
-- the catalogue?  This uses WHERE + GROUP BY + HAVING + ORDER BY together.
SELECT brand,
       COUNT(*)             AS products,
       ROUND(AVG(price), 2) AS avg_price
FROM products
WHERE price > 50000
GROUP BY brand
HAVING COUNT(*) >= 2
ORDER BY avg_price DESC
LIMIT 5;
