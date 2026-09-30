# SQL Results Summary

Executed results for the MySQL layer of the E-Commerce Sales Analysis project.

Every number in this document was produced by running the SQL files in this
folder against the `ecommerce_sales_analysis` database on MySQL 8.0. Nothing is
copied from Phase 2 or estimated. Where a figure is compared with Phase 2, the
comparison was computed by `13_phase2_reconciliation.sql`.

**Reproduce everything in one command:**

```bash
mysql -u root -p --database=ecommerce_sales_analysis < sql/14_headline_metrics.sql
```

---

## Headline metrics

Source: `sql/14_headline_metrics.sql`

| Metric | SQL Result |
| --- | ---: |
| Total Orders | 12,000 |
| Completed Orders | 9,076 |
| Pending Orders | 1,220 |
| Cancelled Orders | 774 |
| Returned Orders | 930 |
| Active Customers | 1,440 |
| Registered Customers | 1,500 |
| Inactive Customers | 60 |
| Repeat Customer Rate | 90.83% |
| Products | 300 |
| Order Lines | 30,006 |
| Units Sold (all orders) | 50,694 |
| Units Sold (completed orders) | 38,406 |
| **Realised Revenue** | **PKR 632,578,305.60** |
| **Realised Profit** | **PKR 196,295,405.60** |
| Overall Margin | 31.03% |
| Gross / Potential Order Value | PKR 845,400,583.33 |
| Average Order Value (AOV) | PKR 69,697.92 |
| Profit per Completed Order | PKR 21,627.96 |
| Lines per Order | 2.50 |
| Units per Order | 4.22 |
| Completion Rate | 75.63% |
| **Cancellation Rate** | **6.45%** |
| **Return Rate** | **7.75%** |
| Pending Rate | 10.17% |
| Discounted Line Share | 51.46% |
| Average Discount (when discounted) | 12.17% |
| Discount Given Away (completed orders) | PKR 44,306,902.65 |
| Top 10 Customers' Share of Realised Revenue | 3.60% |
| Failed Orders (cancelled + returned) as % of gross value | 15.15% |

> **Definition note.** *Realised* always means Completed orders only.
> *Gross / potential* means every order line regardless of status. The two are
> never mixed: the PKR 845.4M gross figure is value that was attempted, the
> PKR 632.6M realised figure is value that was earned.

---

## Order status breakdown

Source: `sql/09_sales_analysis.sql`, section 2

| Status | Orders | Share |
| --- | ---: | ---: |
| Completed | 9,076 | 75.63% |
| Pending | 1,220 | 10.17% |
| Returned | 930 | 7.75% |
| Cancelled | 774 | 6.45% |

## Category performance (realised)

Source: `sql/08_product_analysis.sql`, `sql/09_sales_analysis.sql`

| Category | Realised Revenue | Realised Profit | Margin |
| --- | ---: | ---: | ---: |
| Electronics | 177,321,318.73 | 63,852,068.73 | 36.01% |
| Home Appliances | 158,512,077.59 | 44,890,527.59 | 28.32% |
| Computers | 153,812,523.67 | 49,477,073.67 | 32.17% |
| Home & Kitchen | 42,028,660.26 | 13,371,440.26 | 31.82% |
| Fashion | 26,808,739.67 | 7,058,939.67 | 26.33% |
| Mobile Accessories | 21,893,346.44 | 6,089,126.44 | 27.81% |
| Sports | 18,580,377.78 | 3,690,587.78 | 19.86% |
| Beauty | 18,449,332.13 | 4,365,022.13 | 23.66% |
| Books | 7,878,236.58 | 1,812,916.58 | 23.01% |
| Grocery | 7,293,692.73 | 1,687,702.73 | 23.14% |

The top three categories (Electronics, Home Appliances, Computers) account for
**77.4%** of realised revenue. Margin ranges from **36.01%** (Electronics) to
**19.86%** (Sports).

## City performance (realised, top 5)

Source: `sql/07_customer_analysis.sql`, `sql/09_sales_analysis.sql`

| Shipping City | Realised Revenue | Share |
| --- | ---: | ---: |
| Karachi | 123,442,173.68 | 19.51% |
| Lahore | 119,768,642.21 | 18.93% |
| Islamabad | 58,203,133.39 | 9.20% |
| Rawalpindi | 53,986,138.92 | 8.53% |
| Faisalabad | 44,305,556.38 | 7.00% |

The top five cities account for **63.2%** of realised revenue.

## Top products

Source: `sql/08_product_analysis.sql`, `sql/10_business_questions.sql`

**By units (all orders):**

| Product | Category | Units |
| --- | --- | ---: |
| EBM Peanut Pack | Grocery | 1,568 |
| Dalda Basmati Rice 5kg Hardcover | Grocery | 1,496 |
| My First Activity Book Hardcover | Books | 1,103 |
| Clean & Clear Face Wash | Beauty | 1,061 |
| Continental Chocolatto | Grocery | 889 |

**By realised revenue:**

| Product | Category | Realised Revenue |
| --- | --- | ---: |
| Polaroid Mirrorless Camera | Electronics | 55,289,911.59 |
| GoPro Instant Camera | Electronics | 28,687,811.23 |
| Philips Smart TV | Electronics | 27,681,931.46 |
| Haier Double Door Refrigerator | Home Appliances | 22,644,373.32 |
| Dawlance Twin Tub Washer Paperback | Home Appliances | 22,345,853.72 |

## Discount analysis (completed orders)

Source: `sql/09_sales_analysis.sql`, section 13

| Discount band | Lines | % of lines | Units per line | Revenue per line | Margin |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0% | 11,002 | 48.49% | 1.69 | 29,262.55 | 35.42% |
| 1–5% | 3,893 | 17.16% | 1.70 | 26,629.13 | 32.52% |
| 6–10% | 3,058 | 13.48% | 1.70 | 28,381.79 | 28.85% |
| 11–15% | 2,141 | 9.44% | 1.71 | 26,966.17 | 23.42% |
| 16–20% | 1,415 | 6.24% | 1.66 | 24,500.16 | 19.68% |
| 21–25% | 702 | 3.09% | 1.71 | 23,181.86 | 14.46% |
| 26–30% | 480 | 2.12% | 1.64 | 23,952.11 | 7.14% |

**Pattern:** as the discount band deepens, margin falls steadily from 35.42% to
7.14%, and revenue per line at the deepest band is about **0.82×** the
no-discount band, while units per line stay roughly flat (about **0.97×**).

This is a description of the data, not proof of cause. Product mix, basket size
and which items were promoted all move at the same time, and this is a single
observational dataset, so no causal claim is made.

## Payment analysis

Source: `sql/12_payment_analysis.sql`

| Payment method | Payments | Share |
| --- | ---: | ---: |
| Cash on Delivery | 3,305 | 27.54% |
| Credit Card | 3,119 | 25.99% |
| JazzCash | 1,903 | 15.86% |
| Debit Card | 1,856 | 15.47% |
| EasyPaisa | 1,107 | 9.23% |
| Bank Transfer | 710 | 5.92% |

| Payment status | Payments | Share |
| --- | ---: | ---: |
| Paid | 8,731 | 72.76% |
| Refunded | 1,676 | 13.97% |
| Pending | 1,027 | 8.56% |
| Failed | 566 | 4.72% |

| Payment method | Failure rate |
| --- | ---: |
| JazzCash | 5.31% |
| Debit Card | 5.17% |
| Credit Card | 4.81% |
| Bank Transfer | 4.65% |
| Cash on Delivery | 4.51% |
| EasyPaisa | 3.34% |

Cash on Delivery, Credit Card and JazzCash together account for **69.4%** of
payments. Every one of the 566 failed payments sits on a **Cancelled** order.

## Time trend

Source: `sql/11_advanced_analysis.sql`

| Item | Result |
| --- | ---: |
| Busiest complete month | 2026-08 (669 orders) |
| Quietest complete month | 2024-10 (378 orders) |
| First 6 complete months, avg realised revenue | PKR 22,851,257.14 |
| Last 6 complete months, avg realised revenue | PKR 28,214,852.04 |
| Change | **+23.47%** |

2026-09 is a **partial month** (data ends 2026-09-26) and is excluded from all
trend comparisons.

## Value that did not complete

Source: `sql/10_business_questions.sql`, Q15

| Definition | Orders | Gross value | % of gross revenue |
| --- | ---: | ---: | ---: |
| Payment failed (`payments.payment_status = 'Failed'`) | 566 | 45,414,177.52 | 5.37% |
| Order did not complete (Cancelled or Returned) | 1,704 | 128,110,033.02 | 15.15% |

These are two different questions. "Payment failed" is a payment outcome;
"order did not complete" is an order outcome. Both are labelled as gross /
potential value, because neither was earned.

Worst category by loss rate (lost ÷ (lost + completed)): **Home Appliances**,
**18.75%**, PKR 36,574,525.81.

---

## Data validation

Source: `sql/05_data_validation.sql`

| Result | Count |
| --- | ---: |
| Total checks | 42 |
| Passed | 42 |
| Failed | 0 |

Checks cover row counts against the source CSVs, primary-key uniqueness,
non-null columns, foreign-key integrity, duplicate `(order_id, product_id)`
pairs, date validity, numeric ranges, allowed status values and the
one-payment-per-order relationship.

## Reconciliation with Phase 2

Source: `sql/13_phase2_reconciliation.sql`

| Group | Compared | Match |
| --- | ---: | ---: |
| Headline metrics | 33 | 33 |
| Category revenues | 10 | 10 |
| **Total** | **43** | **43** |

Every headline metric and every category revenue agrees with the Phase 2 pandas
notebook within rounding. Three figures were investigated because they *looked*
different and turned out to be definition differences, not errors; they are
documented in `13_phase2_reconciliation.sql` and in the final Phase 3 report.

---

## Known data characteristics

These are properties of the source data, discovered during validation. None of
them is a data-integrity failure, and nothing was changed to hide them.

| Observation | Detail | Why it matters |
| --- | --- | --- |
| `order_items.unit_price` rarely equals `products.price` | different on 30,005 of 30,006 lines; up to 670 distinct prices per product | `unit_price` is the price actually charged and is the only price used for revenue. `products.price` is the current catalogue price. They are never mixed in one expression. |
| Completed orders with a `Refunded` payment | 635 orders | A refund is a payment outcome, not an order-status outcome. The two are reported separately in `sql/12_payment_analysis.sql`. |
| Product names contain a format suffix | e.g. `Dawlance Twin Tub Washer Paperback`, `Dalda Basmati Rice 5kg Hardcover` | The Phase 1 generator appends a book-format word to keep names unique, and applies it to every category. Cosmetic only; it affects no metric. Reported rather than fixed, because Phase 1 logic must not be modified. |
| 2026-09 is a partial month | data ends 2026-09-26 | Excluded from every month-over-month and period comparison. |

---

## Key findings

1. **Realised revenue is PKR 632.6M against PKR 845.4M attempted** — about
   25% of gross value sits in orders that did not complete.
2. **Revenue is concentrated at the top of the catalogue**: three categories
   carry 77.4% of realised revenue, five cities carry 63.2%.
3. **Customer base is broad, not whale-dependent**: the top 10 customers are
   only 3.60% of realised revenue, while 90.83% of active customers are repeat
   buyers.
4. **Margin falls monotonically with discount depth** (35.42% → 7.14%) with no
   volume lift at deeper bands, which is worth a closer look before deeper
   discounts are used again.
5. **Payment failure is low overall (4.72%)** but clusters by method, with
   JazzCash highest at 5.31%.
6. **The business is growing**: the last six complete months average 23.47%
   more realised revenue than the first six.
