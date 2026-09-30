-- =============================================================================
-- 04_import_notes.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : importing the CSV data
--
-- The five CSV files are the source of truth. NOTHING in data/ is modified to
-- make the import work. The files are read exactly as Phase 1 produced them.
--
-- -----------------------------------------------------------------------------
-- WHY THE CLIENT NEEDS A FLAG
-- -----------------------------------------------------------------------------
-- The CSVs live in the project folder, which is NOT the server's secure-file-priv
-- directory. Server-side LOAD DATA INFILE can only read from secure-file-priv,
-- so the import uses LOAD DATA *LOCAL* INFILE, which streams the file through
-- the mysql client instead. That requires the setting on BOTH sides:
--
--   server :  SET GLOBAL local_infile = 1;        (MySQL 8 ships with it OFF)
--   client :  mysql --local-infile=1 -u root ...
--
-- This file deliberately does NOT change any server setting; that is done once
-- by the operator before running the import, and restored afterwards.
--
-- -----------------------------------------------------------------------------
-- HOW TO RUN THIS FILE
-- -----------------------------------------------------------------------------
--   1. Enable local infile on the server (as root, once per server restart):
--
--        SET GLOBAL local_infile = 1;
--
--   2. Load the tables, in dependency order, from the project root:
--
--        mysql --local-infile=1 -u root --default-character-set=utf8mb4 \
--              < sql/04_import_notes.sql
--
--      On Windows PowerShell:
--
--        Get-Content sql\04_import_notes.sql -Raw |
--            mysql --local-infile=1 -u root --default-character-set=utf8mb4
--
--   3. Restore the server setting if you wish:
--
--        SET GLOBAL local_infile = 0;
--
-- -----------------------------------------------------------------------------
-- FILE FORMAT FACTS (verified from the bytes of each CSV, not assumed)
-- -----------------------------------------------------------------------------
--   character set : UTF-8, no byte-order mark
--   line ending   : CRLF (\r\n)
--   header row    : present, one line, must be skipped -> IGNORE 1 LINES
--   separators    : plain commas, no quoting or escaped characters anywhere,
--                   so OPTIONALLY ENCLOSED BY '"' is stated for safety but is
--                   not actually needed by this data
--
-- -----------------------------------------------------------------------------
-- IMPORT ORDER
-- -----------------------------------------------------------------------------
--   1. customers   (no dependencies)
--   2. products    (no dependencies)
--   3. orders      (needs customers)
--   4. order_items (needs orders and products)
--   5. payments    (needs orders)
--
-- Loading in any other order fails on the foreign keys. That is the constraint
-- working as intended.
-- =============================================================================

USE ecommerce_sales_analysis;

-- Start from empty tables so this file can be re-run without creating
-- duplicates. Foreign keys are temporarily disabled because order_items and
-- payments must be emptied before the tables they point at.
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE payments;
TRUNCATE TABLE order_items;
TRUNCATE TABLE orders;
TRUNCATE TABLE products;
TRUNCATE TABLE customers;
SET FOREIGN_KEY_CHECKS = 1;


-- -----------------------------------------------------------------------------
-- 1. customers
-- -----------------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'C:/Users/HP/Documents/Default Project/E-Commerce-Sales-Analysis/data/customers.csv'
INTO TABLE customers
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(customer_id, name, email, gender, age, city, signup_date);


-- -----------------------------------------------------------------------------
-- 2. products
-- -----------------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'C:/Users/HP/Documents/Default Project/E-Commerce-Sales-Analysis/data/products.csv'
INTO TABLE products
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(product_id, product_name, category, subcategory, brand, price, cost, stock_quantity);


-- -----------------------------------------------------------------------------
-- 3. orders
-- -----------------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'C:/Users/HP/Documents/Default Project/E-Commerce-Sales-Analysis/data/orders.csv'
INTO TABLE orders
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(order_id, customer_id, order_date, status, shipping_city);


-- -----------------------------------------------------------------------------
-- 4. order_items
-- -----------------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'C:/Users/HP/Documents/Default Project/E-Commerce-Sales-Analysis/data/order_items.csv'
INTO TABLE order_items
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(order_item_id, order_id, product_id, quantity, unit_price, discount_percent);


-- -----------------------------------------------------------------------------
-- 5. payments
-- -----------------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'C:/Users/HP/Documents/Default Project/E-Commerce-Sales-Analysis/data/payments.csv'
INTO TABLE payments
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(payment_id, order_id, payment_method, payment_status, payment_date);


-- -----------------------------------------------------------------------------
-- Verify the import immediately. These are the exact row counts published for
-- the Phase 1 dataset. If any number differs, stop and investigate.
-- -----------------------------------------------------------------------------
SELECT 'customers'   AS table_name, COUNT(*) AS rows_imported, 1500   AS expected FROM customers UNION ALL
SELECT 'products',    COUNT(*), 300    FROM products    UNION ALL
SELECT 'orders',      COUNT(*), 12000  FROM orders      UNION ALL
SELECT 'order_items', COUNT(*), 30006  FROM order_items UNION ALL
SELECT 'payments',    COUNT(*), 12000  FROM payments;
