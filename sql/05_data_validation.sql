-- =============================================================================
-- 05_data_validation.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : data validation after import
--
-- Every check runs against the imported MySQL tables and reports the NUMBER OF
-- VIOLATING ROWS. A check passes when that number is 0.
--
-- A common way to fake a "successful" import is to write checks that cannot
-- fail. These are written so they CAN fail: they count rows, and the expected
-- row counts come from the CSV files, which were counted independently before
-- the import.
--
-- The database also enforces much of this structurally (PRIMARY KEY, FOREIGN
-- KEY, NOT NULL, ENUM, CHECK). These queries confirm the enforcement landed.
--
-- The 42 checks are built once as a CTE. Window functions over that CTE add the
-- pass/fail summary to every row, so the list and the summary can never drift
-- apart. `failed` must be 0.
-- =============================================================================

USE ecommerce_sales_analysis;

WITH checks AS (

    -- -------------------------------------------------------------------------
    -- A. ROW COUNTS  (expected = measured line count of each CSV file)
    -- -------------------------------------------------------------------------
    SELECT 1 AS no, 'row count' AS area, 'customers row count = 1500' AS check_name,
           ABS(COUNT(*) - 1500) AS violations FROM customers
    UNION ALL
    SELECT 2, 'row count', 'products row count = 300',
           ABS(COUNT(*) - 300) FROM products
    UNION ALL
    SELECT 3, 'row count', 'orders row count = 12000',
           ABS(COUNT(*) - 12000) FROM orders
    UNION ALL
    SELECT 4, 'row count', 'order_items row count = 30006',
           ABS(COUNT(*) - 30006) FROM order_items
    UNION ALL
    SELECT 5, 'row count', 'payments row count = 12000',
           ABS(COUNT(*) - 12000) FROM payments

    -- -------------------------------------------------------------------------
    -- B. PRIMARY KEY UNIQUENESS
    -- -------------------------------------------------------------------------
    UNION ALL
    SELECT 6, 'primary key', 'customers.customer_id unique',
           COUNT(*) - COUNT(DISTINCT customer_id) FROM customers
    UNION ALL
    SELECT 7, 'primary key', 'products.product_id unique',
           COUNT(*) - COUNT(DISTINCT product_id) FROM products
    UNION ALL
    SELECT 8, 'primary key', 'orders.order_id unique',
           COUNT(*) - COUNT(DISTINCT order_id) FROM orders
    UNION ALL
    SELECT 9, 'primary key', 'order_items.order_item_id unique',
           COUNT(*) - COUNT(DISTINCT order_item_id) FROM order_items
    UNION ALL
    SELECT 10, 'primary key', 'payments.payment_id unique',
           COUNT(*) - COUNT(DISTINCT payment_id) FROM payments

    -- -------------------------------------------------------------------------
    -- C. NULL CHECKS  (11 is structural, 12-15 are runtime spot checks)
    -- -------------------------------------------------------------------------
    UNION ALL
    SELECT 11, 'nulls', 'no nullable columns anywhere in the schema',
           COUNT(*) FROM information_schema.columns
           WHERE table_schema = 'ecommerce_sales_analysis' AND is_nullable = 'YES'
    UNION ALL
    SELECT 12, 'nulls', 'customers.email has no NULLs',
           SUM(email IS NULL) FROM customers
    UNION ALL
    SELECT 13, 'nulls', 'orders.customer_id has no NULLs',
           SUM(customer_id IS NULL) FROM orders
    UNION ALL
    SELECT 14, 'nulls', 'order_items.unit_price has no NULLs',
           SUM(unit_price IS NULL) FROM order_items
    UNION ALL
    SELECT 15, 'nulls', 'payments.order_id has no NULLs',
           SUM(order_id IS NULL) FROM payments

    -- -------------------------------------------------------------------------
    -- D. FOREIGN KEY INTEGRITY
    -- -------------------------------------------------------------------------
    UNION ALL
    SELECT 16, 'foreign key', 'every order has a known customer',
           COUNT(*) FROM orders o
           LEFT JOIN customers c ON c.customer_id = o.customer_id
           WHERE c.customer_id IS NULL
    UNION ALL
    SELECT 17, 'foreign key', 'every order_item has a known order',
           COUNT(*) FROM order_items oi
           LEFT JOIN orders o ON o.order_id = oi.order_id
           WHERE o.order_id IS NULL
    UNION ALL
    SELECT 18, 'foreign key', 'every order_item has a known product',
           COUNT(*) FROM order_items oi
           LEFT JOIN products p ON p.product_id = oi.product_id
           WHERE p.product_id IS NULL
    UNION ALL
    SELECT 19, 'foreign key', 'every payment has a known order',
           COUNT(*) FROM payments p
           LEFT JOIN orders o ON o.order_id = p.order_id
           WHERE o.order_id IS NULL
    UNION ALL
    SELECT 20, 'foreign key', 'exactly 4 foreign key constraints defined',
           ABS(COUNT(*) - 4) FROM information_schema.table_constraints
           WHERE table_schema = 'ecommerce_sales_analysis'
             AND constraint_type = 'FOREIGN KEY'

    -- -------------------------------------------------------------------------
    -- E. DUPLICATE ORDER + PRODUCT COMBINATION
    -- -------------------------------------------------------------------------
    UNION ALL
    SELECT 21, 'uniqueness', 'no duplicate (order_id, product_id) pairs',
           COUNT(*) - COUNT(DISTINCT order_id, product_id) FROM order_items

    -- -------------------------------------------------------------------------
    -- F. DATE VALIDITY  (window measured as 2024-10-01 .. 2026-09-26)
    -- -------------------------------------------------------------------------
    UNION ALL
    SELECT 22, 'dates', 'no order before 2024-10-01',
           SUM(order_date < '2024-10-01') FROM orders
    UNION ALL
    SELECT 23, 'dates', 'no order after 2026-09-26',
           SUM(order_date > '2026-09-26') FROM orders
    UNION ALL
    SELECT 24, 'dates', 'no order dated in the future',
           SUM(order_date > CURDATE()) FROM orders
    UNION ALL
    SELECT 25, 'dates', 'no payment dated before its order',
           COUNT(*) FROM payments p
           JOIN orders o ON o.order_id = p.order_id
           WHERE p.payment_date < o.order_date
    UNION ALL
    SELECT 26, 'dates', 'no customer signs up after their first order',
           COUNT(*) FROM customers c
           JOIN (SELECT customer_id, MIN(order_date) AS first_order
                 FROM orders GROUP BY customer_id) f
             ON f.customer_id = c.customer_id
           WHERE c.signup_date > f.first_order

    -- -------------------------------------------------------------------------
    -- G. NUMERIC VALIDITY
    -- -------------------------------------------------------------------------
    UNION ALL
    SELECT 27, 'numbers', 'quantity always > 0',
           SUM(quantity <= 0) FROM order_items
    UNION ALL
    SELECT 28, 'numbers', 'quantity within documented range 1..5',
           SUM(quantity < 1 OR quantity > 5) FROM order_items
    UNION ALL
    SELECT 29, 'numbers', 'unit_price always > 0',
           SUM(unit_price <= 0) FROM order_items
    UNION ALL
    SELECT 30, 'numbers', 'product price always > 0',
           SUM(price <= 0) FROM products
    UNION ALL
    SELECT 31, 'numbers', 'product cost always > 0',
           SUM(cost <= 0) FROM products
    UNION ALL
    SELECT 32, 'numbers', 'discount_percent between 0 and 30',
           SUM(discount_percent < 0 OR discount_percent > 30) FROM order_items
    UNION ALL
    SELECT 33, 'numbers', 'stock_quantity never negative',
           SUM(stock_quantity < 0) FROM products
    UNION ALL
    SELECT 34, 'numbers', 'cost is always below price (positive margin)',
           SUM(cost >= price) FROM products

    -- -------------------------------------------------------------------------
    -- H. STATUS / CATEGORY VALIDITY
    -- -------------------------------------------------------------------------
    UNION ALL
    SELECT 35, 'status', 'order status in allowed set',
           SUM(status NOT IN ('Completed','Pending','Cancelled','Returned')) FROM orders
    UNION ALL
    SELECT 36, 'status', 'payment status in allowed set',
           SUM(payment_status NOT IN ('Paid','Pending','Failed','Refunded')) FROM payments
    UNION ALL
    SELECT 37, 'status', 'payment method in allowed set',
           SUM(payment_method NOT IN ('Cash on Delivery','Credit Card','Debit Card',
                                      'Bank Transfer','JazzCash','EasyPaisa')) FROM payments
    UNION ALL
    SELECT 38, 'status', 'gender in allowed set',
           SUM(gender NOT IN ('Male','Female')) FROM customers

    -- -------------------------------------------------------------------------
    -- I. PAYMENT RELATIONSHIP  (must be one-to-one)
    -- -------------------------------------------------------------------------
    UNION ALL
    SELECT 39, 'payments', 'order count equals payment count (one per order)',
           (SELECT COUNT(*) FROM orders) - (SELECT COUNT(*) FROM payments)
    UNION ALL
    SELECT 40, 'payments', 'no order has more than one payment',
           COUNT(*) - COUNT(DISTINCT order_id) FROM payments

    -- -------------------------------------------------------------------------
    -- J. COMPLETENESS
    -- -------------------------------------------------------------------------
    UNION ALL
    SELECT 41, 'completeness', 'no order has zero order_items',
           COUNT(*) FROM orders o
           WHERE NOT EXISTS (SELECT 1 FROM order_items oi WHERE oi.order_id = o.order_id)
    UNION ALL
    SELECT 42, 'completeness', 'every order_item product exists in catalogue',
           COUNT(*) FROM order_items oi
           WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = oi.product_id)
)
SELECT no,
       area,
       check_name,
       violations,
       CASE WHEN violations = 0 THEN 'PASS' ELSE 'FAIL' END AS outcome,
       COUNT(*)             OVER () AS total_checks,
       SUM(violations = 0)  OVER () AS passed,
       SUM(violations <> 0) OVER () AS failed
FROM checks
ORDER BY no;
