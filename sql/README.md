# SQL / MySQL Analysis

This folder contains the complete SQL layer of the **E-Commerce Sales Analysis**
project. The same five CSV files that were analysed with pandas in Phase 2 are
loaded into a real MySQL database and analysed again with SQL, from schema
design through to validation and business reporting.

Everything here was executed against MySQL 8.0. No query in this folder is
illustrative-only, and no result is copied from another phase.

---

## Database

| Item | Value |
| --- | --- |
| Database name | `ecommerce_sales_analysis` |
| Engine | InnoDB |
| Character set | `utf8mb4` / `utf8mb4_0900_ai_ci` |
| Server | MySQL 8.0 |
| Money type | `DECIMAL(10,2)` — never `FLOAT` |

---

## Tables

Five tables mirror the five CSV files exactly. Column names match the CSVs so
the SQL maps one-to-one onto the source data.

| Table | Grain | Rows | Primary key |
| --- | --- | ---: | --- |
| `customers` | one row per registered customer | 1,500 | `customer_id` |
| `products` | one row per sellable product | 300 | `product_id` |
| `orders` | one row per order header | 12,000 | `order_id` |
| `order_items` | one row per product line inside an order | 30,006 | `order_item_id` |
| `payments` | one row per order (one payment) | 12,000 | `payment_id` |

### Integrity rules enforced by the schema

- **Primary keys** on all five tables.
- **Foreign keys**:
  `orders.customer_id → customers`, `order_items.order_id → orders`,
  `order_items.product_id → products`, `payments.order_id → orders`.
- **Delete behaviour**: `order_items` and `payments` cascade with their order;
  `customers` and `products` are `RESTRICT`-protected so sales history cannot be
  silently deleted.
- **Unique keys**: `customers.email`, `order_items (order_id, product_id)`, and
  `payments (order_id)`. The last of these is what makes the relationship between
  orders and payments a true **one-to-one**.
- **`CHECK` constraints** on quantity, prices, discounts and age; **`ENUM`s**
  for `gender`, order `status`, `payment_method` and `payment_status` so an
  invalid value cannot be stored.

---

## Relationships

```
customers 1 ────< orders 1 ────< order_items >──── 1 products
                     │
                     └──── 1 payments   (one-to-one)
```

| Relationship | Cardinality |
| --- | --- |
| `customers` → `orders` | one-to-many |
| `orders` → `order_items` | **one-to-many** |
| `products` → `order_items` | one-to-many |
| `orders` → `payments` | **one-to-one** |

---

## How to create the database

```bash
mysql -u root -p < sql/01_create_database.sql
mysql -u root -p < sql/02_create_tables.sql
mysql -u root -p < sql/03_indexes.sql
```

`02_create_tables.sql` drops and recreates the tables, so it is safe to re-run
but it deletes existing data. The CSVs are the source of truth and are never
modified.

## How to import the data

The CSVs live outside the server's `secure-file-priv` directory, so the import
uses `LOAD DATA LOCAL INFILE`, which streams the file through the client.

```bash
# once, on the server
mysql -u root -p -e "SET GLOBAL local_infile = 1;"

# load the five files (paths are absolute, see the file itself)
mysql --local-infile=1 -u root -p --default-character-set=utf8mb4 \
      < sql/04_import_notes.sql

# restore the server setting
mysql -u root -p -e "SET GLOBAL local_infile = 0;"
```

On Windows PowerShell (no `<` redirection):

```powershell
Get-Content sql\04_import_notes.sql -Raw |
    mysql --local-infile=1 -u root --default-character-set=utf8mb4
```

The import file ends with a row-count check against the five source files.

## How to run validation

```bash
mysql -u root -p --database=ecommerce_sales_analysis < sql/05_data_validation.sql
```

This runs 42 checks and prints a `PASS` / `FAIL` outcome for each, plus a live
summary. `failed` must be 0.

## How to run the analysis

Each file is self-contained and can be run on its own, in any order:

```bash
mysql -u root -p --database=ecommerce_sales_analysis < sql/06_basic_analysis.sql
mysql -u root -p --database=ecommerce_sales_analysis < sql/07_customer_analysis.sql
mysql -u root -p --database=ecommerce_sales_analysis < sql/08_product_analysis.sql
mysql -u root -p --database=ecommerce_sales_analysis < sql/09_sales_analysis.sql
mysql -u root -p --database=ecommerce_sales_analysis < sql/10_business_questions.sql
mysql -u root -p --database=ecommerce_sales_analysis < sql/11_advanced_analysis.sql
mysql -u root -p --database=ecommerce_sales_analysis < sql/12_payment_analysis.sql
mysql -u root -p --database=ecommerce_sales_analysis < sql/13_phase2_reconciliation.sql
mysql -u root -p --database=ecommerce_sales_analysis < sql/14_headline_metrics.sql
```

> ### Read-only vs destructive
>
> | File | Effect |
> | --- | --- |
> | `01`–`14` (`05`–`14` for routine work) | `05`–`14` are **read-only** |
> | `02_create_tables.sql` | **destructive** — `DROP TABLE` then recreate, all data lost |
> | `03_indexes.sql` | safe to re-run only if the indexes do not already exist |
> | `04_import_notes.sql` | **destructive** — reloads all five tables from the CSVs |
>
> Never run `02` or `04` in the same batch as the analysis files. If `02` runs
> and `04` then fails (for example because `local_infile` is disabled), the
> database is left empty. Rebuild in this order instead:
>
> ```
> 01 -> 02 -> 03 -> 04 -> 05 -> 06..14
> ```

---

## Metric definitions

These definitions are applied **consistently** in every file. Mixing them is the
most common way an analysis goes wrong.

| Metric | Definition |
| --- | --- |
| **Line revenue** | `quantity * unit_price * (1 - discount_percent / 100)` |
| **Gross / potential order value** | line revenue summed over **all** orders, whatever the status. This is value that was *attempted*. |
| **Realised revenue** | line revenue summed over **Completed orders only**. This is value that was *earned*. |
| **Realised profit** | `line revenue − (quantity * products.cost)` for **Completed orders only** |
| **Margin** | `realised profit / realised revenue * 100` |
| **Average order value (AOV)** | `realised revenue / number of Completed orders` |
| **Active customer** | a registered customer with at least one order |
| **Repeat customer** | an active customer with **more than one** order |
| **Units per order** | `SUM(quantity) / COUNT(orders)` |
| **Lines per order** | `COUNT(order_items) / COUNT(orders)` |

> Realised revenue is **never** called simply "revenue" in ambiguous contexts.
> Whole-dataset figures are always labelled **gross / potential**.

---

## Join and cardinality considerations

This is the single most important correctness rule in the SQL layer.

`orders` → `order_items` is **one-to-many**. `orders` → `payments` is
**one-to-one**. Joining `payments` and `order_items` together on `order_id`
therefore creates a row per *(order line × payment)*, and any `SUM()` of money
across that join would be wrong for a general case.

**Rule followed throughout this folder:** when a query needs facts from two
child tables, the many-side is aggregated to **one row per order first**, and
only then joined.

```sql
-- Safe pattern: collapse order_items to one row per order BEFORE joining
WITH order_value AS (
    SELECT oi.order_id,
           SUM(oi.quantity * oi.unit_price
               * (1 - oi.discount_percent / 100)) AS order_value
    FROM order_items oi
    GROUP BY oi.order_id
)
SELECT p.payment_status,
       COUNT(*)                            AS orders,
       ROUND(SUM(ov.order_value), 2)       AS gross_order_value
FROM payments p
JOIN order_value ov ON ov.order_id = p.order_id
GROUP BY p.payment_status;
```

- Every monetary aggregation runs over a set containing **at most one row per
  order**, and `COUNT(*)` counts orders, not lines.
- Where `payments` is joined to `orders` alone, no monetary `SUM()` is taken, so
  no fan-out is possible.
- `13_phase2_reconciliation.sql`, `05_data_validation.sql` and
  `14_headline_metrics.sql` use scalar subqueries over single tables, so no
  cross-child multiplication can occur at all.

Additional correctness notes:

- `order_items.unit_price` is the price **actually charged** and is usually
  different from `products.price` (the current catalogue price). They are never
  mixed in the same expression.
- `order_items.discount_percent` is a percentage (0–30 in this dataset), applied
  to revenue only, never to cost.

---

## SQL concepts demonstrated

| Concept | Where |
| --- | --- |
| `SELECT`, `WHERE`, `ORDER BY`, `LIMIT`, `DISTINCT` | `06_basic_analysis.sql` |
| `BETWEEN`, `IN`, `LIKE`, `CASE` | `06_basic_analysis.sql` |
| Aggregate functions, `GROUP BY`, `HAVING` | `06`, `07`, `08`, `09` |
| Column and table aliases | all files |
| Multi-table `INNER JOIN`, `LEFT JOIN` | `05`, `07`, `08`, `09` |
| Ratios and percentage contribution | `07`, `09`, `11` |
| Date functions (`DATE_FORMAT`, `YEAR`, `DATEDIFF`) | `09`, `11`, `12` |
| `COUNT(DISTINCT ...)` | `05`, `07` |
| Subqueries (scalar and derived table) | `10`, `11`, `13`, `14` |
| Correlated subqueries | `11_advanced_analysis.sql` |
| CTEs (`WITH`) | `10`, `11`, `12`, `13` |
| Window functions (`ROW_NUMBER`, `RANK`, `DENSE_RANK`, `LAG`, `SUM() OVER`) | `11` |
| Running totals and month-over-month change | `11` |
| Top-N-per-group with `PARTITION BY` | `11` |
| Median without a built-in function | `07` |
| Referential / integrity validation patterns | `05` |
| Cardinality-safe aggregation of a one-to-many relation | `10`, `12` |
| Definition reconciliation against a prior phase | `13` |

---

## Files

| File | Purpose |
| --- | --- |
| `01_create_database.sql` | create and select the database |
| `02_create_tables.sql` | five tables with keys and constraints |
| `03_indexes.sql` | indexes, with rationale for what is *not* indexed |
| `04_import_notes.sql` | `LOAD DATA LOCAL INFILE` import + verification |
| `05_data_validation.sql` | 42 integrity checks |
| `06_basic_analysis.sql` | core SQL technique tour |
| `07_customer_analysis.sql` | customer metrics |
| `08_product_analysis.sql` | product, category and margin metrics |
| `09_sales_analysis.sql` | sales trends and discount analysis |
| `10_business_questions.sql` | the twenty business questions |
| `11_advanced_analysis.sql` | CTEs and window functions |
| `12_payment_analysis.sql` | payment methods, failures, refunds |
| `13_phase2_reconciliation.sql` | SQL vs Phase 2, metric by metric |
| `14_headline_metrics.sql` | one-command scorecard |
| `sql_results_summary.md` | the executed results |
