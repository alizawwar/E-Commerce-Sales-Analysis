-- =============================================================================
-- 12_payment_analysis.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : payment analysis
--
-- This file exists because `payments` is its own table with its own facts, and
-- the payment story is not the same as the order story:
--   * a payment can fail while the order is still recorded
--   * a payment can be refunded while the order is Returned or Cancelled
--   * a payment can be Pending while the order is still Pending
--
-- -----------------------------------------------------------------------------
-- JOIN CARDINALITY - THE RULE THIS FILE FOLLOWS
-- -----------------------------------------------------------------------------
-- `payments` is one row per order (enforced by UNIQUE(order_id)), but
-- `order_items` is MANY rows per order. Joining the two tables directly on
-- order_id therefore DOES multiply rows, and any SUM() placed across that join
-- would count each order's revenue once per payment-match - i.e. it would still
-- be correct here only by luck, because payments happens to be 1:1.
--
-- That luck is not a design. The safe, self-documenting pattern is used instead:
--
--     1. aggregate order_items down to ONE row per order inside a CTE
--     2. join that order-level result to payments (1 row per order)
--     3. aggregate the joined result
--
-- At no point is a monetary SUM() taken over a set of rows that can contain more
-- than one row per order. Where payments is joined to orders alone, no monetary
-- aggregation happens, so no fan-out is possible either.
-- =============================================================================

USE ecommerce_sales_analysis;


-- =============================================================================
-- 1. Payment method usage
-- =============================================================================
SELECT payment_method,
       COUNT(*)                                                   AS payments,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM payments), 2) AS pct_of_payments
FROM payments
GROUP BY payment_method
ORDER BY payments DESC;


-- =============================================================================
-- 2. Payment status distribution
-- =============================================================================
SELECT payment_status,
       COUNT(*)                                                   AS payments,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM payments), 2) AS pct_of_payments
FROM payments
GROUP BY payment_status
ORDER BY payments DESC;


-- =============================================================================
-- 3. Failure rate and success rate by method
-- =============================================================================
-- Success means the payment reached 'Paid'. Refunded money was successfully
-- collected once and then given back, so it is counted separately, not as a
-- failure.
SELECT payment_method,
       COUNT(*)                                                       AS payments,
       SUM(payment_status = 'Paid')                                   AS paid,
       SUM(payment_status = 'Failed')                                 AS failed,
       SUM(payment_status = 'Refunded')                               AS refunded,
       SUM(payment_status = 'Pending')                                AS pending,
       ROUND(100 * SUM(payment_status = 'Failed') / COUNT(*), 2)      AS failure_rate_pct,
       ROUND(100 * SUM(payment_status = 'Paid')   / COUNT(*), 2)      AS paid_rate_pct
FROM payments
GROUP BY payment_method
ORDER BY failure_rate_pct DESC;


-- =============================================================================
-- 4. Payment status against order status
-- =============================================================================
-- A crosstab, which is the clearest way to see that a failed payment almost
-- always sits on an order that was cancelled.
SELECT p.payment_status,
       SUM(o.status = 'Completed') AS completed,
       SUM(o.status = 'Pending')   AS pending,
       SUM(o.status = 'Cancelled') AS cancelled,
       SUM(o.status = 'Returned')  AS returned,
       COUNT(*)                    AS total
FROM payments p
JOIN orders o ON o.order_id = p.order_id
GROUP BY p.payment_status
ORDER BY total DESC;


-- =============================================================================
-- 5. Gross order value by payment status
-- =============================================================================
-- How much order value is attached to each payment outcome. Gross, because the
-- question is about what was attempted, and a failed payment has no realised
-- value by definition.
--
-- CARDINALITY: order_items is collapsed to one row per order FIRST, then joined
-- to payments. The SUM therefore runs over one row per order, never over the
-- many order-item lines.
WITH order_value AS (
    SELECT oi.order_id,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS order_gross_value
    FROM order_items oi
    GROUP BY oi.order_id
)
SELECT p.payment_status,
       COUNT(*)                                        AS orders,
       ROUND(SUM(ov.order_gross_value), 2)             AS gross_order_value
FROM payments p
JOIN order_value ov ON ov.order_id = p.order_id
GROUP BY p.payment_status
ORDER BY gross_order_value DESC;


-- =============================================================================
-- 6. Realised revenue by payment method
-- =============================================================================
-- Realised revenue = revenue from Completed orders only. The order-level CTE
-- restricts to Completed orders and produces exactly one row per order, so the
-- join to payments cannot duplicate revenue and COUNT(*) is already a count of
-- completed orders.
WITH order_value AS (
    SELECT oi.order_id,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS order_realised_revenue
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY oi.order_id
)
SELECT p.payment_method,
       COUNT(*)                                 AS completed_orders,
       ROUND(SUM(ov.order_realised_revenue), 2) AS realised_revenue,
       ROUND(AVG(ov.order_realised_revenue), 2) AS avg_order_value
FROM payments p
JOIN order_value ov ON ov.order_id = p.order_id
GROUP BY p.payment_method
ORDER BY realised_revenue DESC;


-- =============================================================================
-- 7. How long customers take to pay, by method
-- =============================================================================
-- Measured in whole days from the order date to the payment date. Cash on
-- Delivery is expected to settle on or after delivery; cards and wallets can be
-- immediate.
SELECT p.payment_method,
       COUNT(*)                                                AS payments,
       ROUND(AVG(DATEDIFF(p.payment_date, o.order_date)), 2)   AS avg_days_to_payment,
       MIN(DATEDIFF(p.payment_date, o.order_date))             AS min_days,
       MAX(DATEDIFF(p.payment_date, o.order_date))             AS max_days
FROM payments p
JOIN orders o ON o.order_id = p.order_id
GROUP BY p.payment_method
ORDER BY avg_days_to_payment DESC;


-- =============================================================================
-- 8. Refund exposure
-- =============================================================================
-- Value that was collected and then refunded. This is real money leaving the
-- business, so it is worth isolating from failed payments.
-- CARDINALITY: order_items is aggregated to one row per order before the join,
-- so COUNT(*) counts payments and SUM() never double-counts an order's lines.
WITH order_value AS (
    SELECT oi.order_id,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS order_gross_value
    FROM order_items oi
    GROUP BY oi.order_id
)
SELECT COUNT(*)                                          AS refunded_payments,
       ROUND(SUM(ov.order_gross_value), 2)               AS gross_value_refunded,
       ROUND(100 * SUM(ov.order_gross_value)
             / (SELECT SUM(oi2.quantity * oi2.unit_price
                           * (1 - oi2.discount_percent / 100))
                FROM order_items oi2), 2)                AS pct_of_gross_revenue
FROM payments p
JOIN order_value ov ON ov.order_id = p.order_id
WHERE p.payment_status = 'Refunded';


-- =============================================================================
-- 9. Do failed payments cluster in particular cities?
-- =============================================================================
-- Useful operationally: a city with an unusually high failure rate may point at
-- a local courier or wallet problem rather than a customer problem.
SELECT o.shipping_city,
       COUNT(*)                                                    AS payments,
       SUM(p.payment_status = 'Failed')                            AS failed_payments,
       ROUND(100 * SUM(p.payment_status = 'Failed') / COUNT(*), 2) AS failure_rate_pct
FROM payments p
JOIN orders o ON o.order_id = p.order_id
GROUP BY o.shipping_city
ORDER BY failure_rate_pct DESC
LIMIT 10;
