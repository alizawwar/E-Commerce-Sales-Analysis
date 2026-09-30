-- =============================================================================
-- 01_create_database.sql
-- =============================================================================
-- E-Commerce Sales Analysis  |  Phase 3 : MySQL database & SQL analysis
--
-- PURPOSE
--   Create the analysis database and select it. Nothing else is created here,
--   so the script is completely safe to run more than once.
--
-- RUN
--   mysql -u root -p < sql/01_create_database.sql
--   (or paste it into MySQL Workbench and execute)
--
-- DESIGN NOTES
--   * utf8mb4 is used so text is stored correctly no matter what characters
--     appear in customer names or product names.
--   * utf8mb4_0900_ai_ci is the MySQL 8 default collation: case-insensitive,
--     accent-insensitive. That is fine for this dataset, where names are
--     written in plain Latin letters.
--   * No dedicated application user is created, because creating users changes
--     the server and is not needed for a local analysis project. In a real
--     deployment you would create a least-privilege user instead of using root.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS ecommerce_sales_analysis
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE ecommerce_sales_analysis;

-- Confirm which database is now selected, and what is in it (empty first time).
SELECT DATABASE() AS current_database;

SELECT COUNT(*) AS existing_table_count
FROM information_schema.tables
WHERE table_schema = 'ecommerce_sales_analysis';
