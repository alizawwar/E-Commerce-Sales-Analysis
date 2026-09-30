-- =============================================================================
-- 02_create_tables.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : table definitions
--
-- PURPOSE
--   Create the five tables that mirror the five CSV files, with primary keys,
--   foreign keys and value constraints that make illegal data impossible to
--   insert.
--
-- WARNING - THIS SCRIPT DELETES THE EXISTING TABLES
--   It drops and recreates them so that it can be re-run cleanly from scratch.
--   The CSV files are the source of truth and are never touched; the data is
--   re-imported by the import step described in 04_import_notes.sql.
--
-- COLUMN WIDTHS
--   Widths for the code columns are the measured maximum length in the CSV
--   (customer_id = 10, order_id = 10, product_id = 9, order_item_id = 11,
--   payment_id = 10). Free-text columns are given sensible headroom. Because
--   the server runs with STRICT_TRANS_TABLES, a value that is too long or of
--   the wrong type is rejected instead of being silently truncated.
--
-- MONEY
--   DECIMAL, never FLOAT. FLOAT stores binary fractions and produces rounding
--   errors (0.1 + 0.2 <> 0.3), which is unacceptable for money. DECIMAL stores
--   exact decimal values. DECIMAL(10,2) holds up to 99,999,999.99, well above
--   the largest value in the data (unit_price max 385,790.79).
--
-- ENUM vs VARCHAR
--   status, gender, payment_method and payment_status are ENUMs. The set of
--   allowed values was verified from the CSV, and an ENUM makes an invalid
--   value impossible to insert. The trade-off is that adding a new status later
--   needs an ALTER TABLE. That is the right trade for a small, stable list.
--
-- DELETE BEHAVIOUR (why not CASCADE everywhere)
--   * orders -> customers      : RESTRICT. A customer with orders must not be
--     silently deletable, because that would destroy sales history.
--   * order_items -> orders    : CASCADE. Order lines have no meaning without
--     their order, so they should disappear with it.
--   * payments -> orders       : CASCADE. A payment belongs to exactly one
--     order and cannot exist on its own.
--   * order_items -> products  : RESTRICT. Deleting a product that has been
--     sold would rewrite history.
-- =============================================================================

USE ecommerce_sales_analysis;

-- Drop children before parents, otherwise the foreign keys block the drop.
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;
SET FOREIGN_KEY_CHECKS = 1;


-- -----------------------------------------------------------------------------
-- customers  (1 row per registered customer)
-- -----------------------------------------------------------------------------
CREATE TABLE customers (
    customer_id  VARCHAR(10)  NOT NULL                 COMMENT 'Business key, e.g. CUST-00001',
    name         VARCHAR(50)  NOT NULL                 COMMENT 'Full name',
    email        VARCHAR(100) NOT NULL                 COMMENT 'Must be unique',
    gender       ENUM('Male','Female') NOT NULL,
    age          TINYINT UNSIGNED NOT NULL             COMMENT '18-65 in this dataset',
    city         VARCHAR(50)  NOT NULL                 COMMENT 'Customer city',
    signup_date  DATE         NOT NULL,
    PRIMARY KEY (customer_id),
    UNIQUE KEY uq_customers_email (email),
    CONSTRAINT chk_customers_age      CHECK (age BETWEEN 18 AND 100),
    CONSTRAINT chk_customers_email    CHECK (email LIKE '%_@_%')
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci
  COMMENT = 'Registered customers';


-- -----------------------------------------------------------------------------
-- products  (1 row per sellable product)
-- -----------------------------------------------------------------------------
-- Note: the CSV has no rating column, so none is created here.
-- `price` is the current CATALOGUE price. The price actually charged on a sale
-- lives on order_items.unit_price and is not always the same.
CREATE TABLE products (
    product_id      VARCHAR(9)   NOT NULL              COMMENT 'Business key, e.g. PROD-0001',
    product_name    VARCHAR(100) NOT NULL,
    category        VARCHAR(50)  NOT NULL,
    subcategory     VARCHAR(50)  NOT NULL,
    brand           VARCHAR(50)  NOT NULL,
    price           DECIMAL(10,2) NOT NULL             COMMENT 'Current catalogue price, PKR',
    cost            DECIMAL(10,2) NOT NULL             COMMENT 'Unit cost to the business, PKR',
    stock_quantity  SMALLINT UNSIGNED NOT NULL         COMMENT 'Units on hand',
    PRIMARY KEY (product_id),
    CONSTRAINT chk_products_price CHECK (price > 0),
    CONSTRAINT chk_products_cost  CHECK (cost > 0),
    CONSTRAINT chk_products_cogs  CHECK (cost < price) -- every product must earn a margin
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci
  COMMENT = 'Product catalogue with price, cost and stock';


-- -----------------------------------------------------------------------------
-- orders  (1 row per order)
-- -----------------------------------------------------------------------------
-- The CSV column is called `status`; the same name is kept here so the SQL
-- maps one-to-one onto the file and there is no ambiguity when reproducing the
-- Phase 2 numbers.
CREATE TABLE orders (
    order_id       VARCHAR(10) NOT NULL                COMMENT 'Business key, e.g. ORD-000001',
    customer_id    VARCHAR(10) NOT NULL                COMMENT 'Who placed the order',
    order_date     DATE        NOT NULL,
    status         ENUM('Completed','Pending','Cancelled','Returned') NOT NULL
                                                       COMMENT 'Order lifecycle state',
    shipping_city  VARCHAR(50) NOT NULL,
    PRIMARY KEY (order_id),
    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci
  COMMENT = 'Order header';


-- -----------------------------------------------------------------------------
-- order_items  (1 row per product line inside an order)
-- -----------------------------------------------------------------------------
-- This is the table that holds money. Revenue is deliberately NOT stored as a
-- column: it is calculated as
--     quantity * unit_price * (1 - discount_percent / 100)
-- exactly as specified for this project, so the CSV stays the single source of
-- truth and no derived figure can go stale.
CREATE TABLE order_items (
    order_item_id     VARCHAR(11) NOT NULL             COMMENT 'Business key, e.g. ITEM-000001',
    order_id          VARCHAR(10) NOT NULL,
    product_id        VARCHAR(9)  NOT NULL,
    quantity          TINYINT UNSIGNED NOT NULL        COMMENT '1-5 in this dataset',
    unit_price        DECIMAL(10,2) NOT NULL           COMMENT 'Price actually charged per unit, PKR',
    discount_percent  TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0-30',
    PRIMARY KEY (order_item_id),
    -- A product can only appear once per order, which is also how Phase 1 and
    -- Phase 2 treat the data. This unique key makes a duplicate impossible.
    UNIQUE KEY uq_order_items_order_product (order_id, product_id),
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) REFERENCES orders (order_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id) REFERENCES products (product_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_order_items_quantity CHECK (quantity >= 1),
    CONSTRAINT chk_order_items_price    CHECK (unit_price > 0),
    CONSTRAINT chk_order_items_discount CHECK (discount_percent BETWEEN 0 AND 100)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci
  COMMENT = 'Product lines within an order';


-- -----------------------------------------------------------------------------
-- payments  (exactly 1 row per order - a true 1-to-1 relationship)
-- -----------------------------------------------------------------------------
-- Note: the CSV has no amount column, so none is created. Payment value is
-- derived from the order lines when it is needed.
-- The UNIQUE key on order_id is what enforces the 1-to-1 link: without it the
-- relationship would be 1-to-many and joining payments to orders would begin to
-- duplicate rows.
CREATE TABLE payments (
    payment_id      VARCHAR(10) NOT NULL               COMMENT 'Business key, e.g. PAY-000001',
    order_id        VARCHAR(10) NOT NULL               COMMENT 'One payment per order',
    payment_method  ENUM('Cash on Delivery','Credit Card','Debit Card',
                         'Bank Transfer','JazzCash','EasyPaisa') NOT NULL,
    payment_status  ENUM('Paid','Pending','Failed','Refunded') NOT NULL,
    payment_date    DATE        NOT NULL,
    PRIMARY KEY (payment_id),
    UNIQUE KEY uq_payments_order (order_id),
    CONSTRAINT fk_payments_order
        FOREIGN KEY (order_id) REFERENCES orders (order_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci
  COMMENT = 'One payment record per order';

-- Confirm what was created.
SHOW TABLES;
