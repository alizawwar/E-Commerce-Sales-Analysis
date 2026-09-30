-- =============================================================================
-- 03_indexes.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : indexes
--
-- WHY NOT INDEX EVERYTHING
--   Every index speeds up reads but slows down writes and consumes memory. The
--   five tables here hold 55,506 rows in total, which MySQL can scan very
--   quickly anyway. The indexes below are the ones that genuinely match the
--   access patterns used later in this project. Low-selectivity columns and
--   columns that are never filtered on are deliberately left unindexed.
--
-- IMPORTANT - InnoDB ALREADY CREATES SOME INDEXES FOR US
--   InnoDB requires an index on the child side of every foreign key, so it
--   creates one automatically if none exists. That means these already exist
--   and are NOT created again below:
--
--     orders.customer_id        -> created by fk_orders_customer
--     order_items.order_id      -> created by fk_order_items_order
--     order_items.product_id    -> created by fk_order_items_product
--     payments.order_id         -> created by the UNIQUE key uq_payments_order
--
--   Creating them again would be pure duplication, so it is not done.
--
-- NOT INDEXED, AND WHY
--   * order_items.discount_percent - only 7 distinct values. An index on such a
--     low-selectivity column is almost never chosen by the optimiser, and every
--     discount query in this project aggregates all lines anyway.
--   * orders.status on its own    - 4 distinct values and no query filters on
--     status without also touching the date, so the composite index
--     (status, order_date) covers it through its leftmost prefix instead.
--   * products.brand              - 137 distinct values, but brand is not used
--     in any required analysis query.
-- =============================================================================

USE ecommerce_sales_analysis;


-- 1. Orders by date.
--    Used by every monthly and yearly trend query, and by date-range filters.
--    Also lets MySQL return rows in date order without a sort.
CREATE INDEX idx_orders_order_date
    ON orders (order_date);


-- 2. Realised revenue over time.
--    The single most repeated pattern in this project is
--    "revenue of COMPLETED orders grouped by month", i.e. filter on status
--    then group by order_date. A composite index in this column order lets
--    MySQL jump straight to the Completed rows already sorted by date.
--    Because status is the leftmost column, this also serves queries that
--    filter on status alone, so no separate status index is needed.
CREATE INDEX idx_orders_status_date
    ON orders (status, order_date);


-- 3. Orders and revenue by shipping city.
CREATE INDEX idx_orders_shipping_city
    ON orders (shipping_city);


-- 4. Customers by city.
--    Customer-count-by-city and customers-per-city analysis filter on this
--    column; it is not a foreign key, so no index exists for it yet.
CREATE INDEX idx_customers_city
    ON customers (city);


-- 5. Product roll-ups.
--    Category and subcategory performance is grouped both by category alone and
--    by category + subcategory. A composite index with category first serves
--    both, because a query filtering only on category can use the leftmost
--    prefix of the index.
CREATE INDEX idx_products_category_subcategory
    ON products (category, subcategory);


-- 6. Payment status distribution and status-based joins.
CREATE INDEX idx_payments_payment_status
    ON payments (payment_status);


-- 7. Payment method distribution.
CREATE INDEX idx_payments_payment_method
    ON payments (payment_method);


-- Confirm the indexes that exist on each table (including the automatic ones).
SELECT table_name, index_name, seq_in_index, column_name, non_unique
FROM information_schema.statistics
WHERE table_schema = 'ecommerce_sales_analysis'
ORDER BY table_name, index_name, seq_in_index;
