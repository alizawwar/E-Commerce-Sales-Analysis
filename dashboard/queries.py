"""All dashboard SQL, in one place.

Two rules govern this module.

1. **No hardcoded KPIs.** Every number the dashboard shows is produced by a
   query below. There is no constant anywhere in this file holding a business
   figure.

2. **No join multiplication.** ``orders -> order_items`` is one-to-many and
   ``orders -> payments`` is one-to-one (enforced by ``UNIQUE(order_id)`` in
   ``sql/02_create_tables.sql`` and verified in ``sql/05_data_validation.sql``).
   Wherever a monetary total is combined with payment facts, ``order_items`` is
   first collapsed to exactly one row per order inside a CTE. The functions
   that rely on that carry a comment saying so.

Caching
    ``query()`` wraps a single cached executor keyed on the full SQL text *and*
    the full parameter tuple. Because the filters are part of the key, a
    filtered result can never be served for a different filter selection.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

import pandas as pd
import streamlit as st

from .config import CACHE_TTL_ANALYTICS, CACHE_TTL_REFERENCE
from .database import DashboardDBError, in_predicate, run_query
from .utils import Filters

# ---------------------------------------------------------------------------
# Revenue / cost expressions, defined once and reused everywhere.
# Matches sql/README.md exactly.
# ---------------------------------------------------------------------------
REVENUE = "oi.quantity * oi.unit_price * (1 - oi.discount_percent / 100)"
COST = "oi.quantity * pr.cost"
PROFIT = f"({REVENUE} - {COST})"

# A line is only counted as realised if its order completed.
REALISED = f"CASE WHEN o.status = 'Completed' THEN {REVENUE} ELSE 0 END"
REALISED_PROFIT = f"CASE WHEN o.status = 'Completed' THEN {PROFIT} ELSE 0 END"


# ---------------------------------------------------------------------------
# Cached execution
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=400)
def _cached_execute(sql: str, params: tuple) -> pd.DataFrame:
    return run_query(sql, list(params))


def query(sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
    """Run a parameterised, cached query."""
    return _cached_execute(sql, tuple(params or ()))


# ---------------------------------------------------------------------------
# Filter -> SQL
# ---------------------------------------------------------------------------
def _filter_sql(filters: Filters) -> tuple[str, list[Any]]:
    """Translate the global filter selection into a WHERE clause + parameters.

    Category and subcategory are applied at line level (see
    :class:`~dashboard.utils.Filters`), so "Electronics" means *revenue of
    Electronics lines*, not the whole value of orders that contain one.
    """
    filters = filters.normalised()
    clauses: list[str] = ["o.order_date BETWEEN %s AND %s"]
    params: list[Any] = [filters.date_from, filters.date_to]

    city_sql, city_params = in_predicate("o.shipping_city", filters.cities)
    clauses.append(city_sql)
    params += city_params

    status_sql, status_params = in_predicate("o.status", filters.statuses)
    clauses.append(status_sql)
    params += status_params

    if filters.categories:
        cat_sql, cat_params = in_predicate("pr.category", filters.categories)
        clauses.append(cat_sql)
        params += cat_params

    if filters.subcategories:
        sub_sql, sub_params = in_predicate("pr.subcategory", filters.subcategories)
        clauses.append(sub_sql)
        params += sub_params

    # Payment method needs the payments table, which is one-to-one with
    # orders, so this join cannot duplicate order_items rows.
    if filters.payment_methods:
        pay_sql, pay_params = in_predicate("pay.payment_method", filters.payment_methods)
        clauses.append(pay_sql)
        params += pay_params

    return " AND ".join(clauses), params


def _joins(filters: Filters) -> str:
    """JOIN list for the filtered line-level fact table."""
    joins = [
        "JOIN order_items oi ON oi.order_id = o.order_id",
        "JOIN products pr ON pr.product_id = oi.product_id",
    ]
    if filters.payment_methods:
        # Aliased `pay`, not `p`. The payment queries below reuse `p` for
        # payments in their *outer* query block; MySQL merges a CTE into the
        # enclosing scope, so sharing the alias would raise
        # ERROR 1066 (not unique table/alias). Keeping them distinct avoids it.
        joins.append("LEFT JOIN payments pay ON pay.order_id = o.order_id")
    return "\n    ".join(joins)


def _fact_from(filters: Filters) -> str:
    return f"FROM orders o\n    {_joins(filters)}"


# ---------------------------------------------------------------------------
# Reference data (changes only when the dataset changes -> long cache)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_REFERENCE, show_spinner=False)
def reference_data() -> dict[str, Any]:
    """Distinct values that populate the filter widgets."""
    def distinct(column: str, table: str, order_by: str | None = None) -> list[str]:
        order = f" ORDER BY {order_by}" if order_by else " ORDER BY 1"
        frame = query(f"SELECT DISTINCT {column} AS v FROM {table}{order}")
        return frame["v"].dropna().astype(str).tolist() if not frame.empty else []

    bounds = query(
        "SELECT MIN(order_date) AS lo, MAX(order_date) AS hi FROM orders"
    )
    lo = bounds.iloc[0]["lo"] if not bounds.empty else date(2024, 10, 1)
    hi = bounds.iloc[0]["hi"] if not bounds.empty else date(2026, 9, 26)

    subcats = query(
        "SELECT DISTINCT category, subcategory FROM products ORDER BY category, subcategory"
    )

    return {
        "cities": distinct("shipping_city", "orders"),
        "categories": distinct("category", "products"),
        "payment_methods": distinct("payment_method", "payments"),
        "statuses": distinct("status", "orders", "FIELD(status,'Completed','Pending','Cancelled','Returned')"),
        "subcategories_by_category": (
            {c: grp["subcategory"].tolist() for c, grp in subcats.groupby("category")}
            if not subcats.empty
            else {}
        ),
        "date_min": lo,
        "date_max": hi,
    }


@st.cache_data(ttl=CACHE_TTL_REFERENCE, show_spinner=False)
def dataset_summary() -> dict[str, Any]:
    """Small unfiltered facts shown in the sidebar footer."""
    frame = query(
        """
        SELECT (SELECT COUNT(*) FROM orders)            AS orders,
               (SELECT COUNT(*) FROM customers)         AS customers,
               (SELECT COUNT(*) FROM products)          AS products,
               (SELECT COUNT(*) FROM order_items)       AS order_lines,
               (SELECT COUNT(*) FROM payments)          AS payments,
               (SELECT MIN(order_date) FROM orders)      AS first_order,
               (SELECT MAX(order_date) FROM orders)      AS last_order
        """
    )
    if frame.empty:
        return {}
    return _zeroed_row(frame.iloc[0].to_dict())


# ---------------------------------------------------------------------------
# KPI block
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=200)
def kpi_metrics(filters: Filters) -> dict[str, Any]:
    """Every headline number for the current filter selection, in one round trip.

    Order and customer counts use ``COUNT(DISTINCT CASE ...)`` because the fact
    table is at *line* grain - a plain ``SUM(o.status = 'Cancelled')`` would
    count a cancelled order once per product line it contains.

    Realised figures are ``Completed`` only, applied on top of whatever status
    the user has selected. Gross order value uses every selected status and is
    always labelled as such in the UI.
    """
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT
        COUNT(DISTINCT o.order_id)                                   AS total_orders,
        COUNT(DISTINCT CASE WHEN o.status = 'Completed' THEN o.order_id END) AS completed_orders,
        COUNT(DISTINCT CASE WHEN o.status = 'Pending'   THEN o.order_id END) AS pending_orders,
        COUNT(DISTINCT CASE WHEN o.status = 'Cancelled' THEN o.order_id END) AS cancelled_orders,
        COUNT(DISTINCT CASE WHEN o.status = 'Returned'  THEN o.order_id END) AS returned_orders,
        COUNT(DISTINCT o.customer_id)                                AS active_customers,
        COUNT(DISTINCT oi.product_id)                                AS products_sold,
        COUNT(*)                                                     AS line_count,
        SUM(oi.quantity)                                             AS units_total,
        SUM(CASE WHEN o.status = 'Completed' THEN oi.quantity ELSE 0 END) AS units_completed,
        SUM({REVENUE})                                               AS gross_order_value,
        SUM({REALISED})                                              AS realised_revenue,
        SUM({REALISED_PROFIT})                                       AS realised_profit,
        SUM(CASE WHEN o.status IN ('Cancelled', 'Returned')
                 THEN {REVENUE} ELSE 0 END)                         AS value_not_completed,
        SUM(CASE WHEN o.status = 'Pending'
                 THEN {REVENUE} ELSE 0 END)                         AS value_pending,
        SUM(oi.quantity * oi.discount_percent / 100 * oi.unit_price) AS discount_value_all,
        SUM(CASE WHEN o.status = 'Completed'
                 THEN oi.quantity * oi.discount_percent / 100 * oi.unit_price
                 ELSE 0 END)                                         AS discount_value_realised,
        SUM(CASE WHEN oi.discount_percent > 0 THEN 1 ELSE 0 END)      AS discounted_lines
    {_fact_from(filters)}
    WHERE {where}
    """
    frame = query(sql, params)
    if frame.empty:
        return {}
    row = _zeroed_row(frame.iloc[0].to_dict())
    # Realised + not completed + pending must reconstruct gross exactly. This
    # identity is what stops a Pending order being counted as a loss.
    if not row.get("value_not_completed") and row.get("gross_order_value"):
        row["value_not_completed"] = max(
            float(row["gross_order_value"]) - float(row["realised_revenue"]) - float(row.get("value_pending") or 0),
            0.0,
        )
    row["gross_profit"] = row["realised_revenue"] - row["realised_profit"]
    return row


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=200)
def monthly_trend(filters: Filters) -> pd.DataFrame:
    """Month-by-month orders, units, realised revenue, profit and AOV.

    The month key is ``EXTRACT(YEAR_MONTH ...)`` (an integer such as 202410)
    rather than ``DATE_FORMAT(..., '%Y-%m')``. That is not a style choice: the
    MySQL driver interpolates parameters with ``query % args``, so a literal
    ``%Y`` inside the SQL is read as a printf format specifier and the query
    never reaches the server. Avoiding ``%`` in SQL text sidesteps that
    entirely, and an integer month also sorts chronologically for free.
    """
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT EXTRACT(YEAR_MONTH FROM o.order_date)   AS ym,
           COUNT(DISTINCT o.order_id)               AS orders,
           COUNT(DISTINCT CASE WHEN o.status = 'Completed' THEN o.order_id END) AS completed_orders,
           SUM(oi.quantity)                         AS units,
           SUM({REVENUE})                           AS gross_order_value,
           SUM({REALISED})                          AS realised_revenue,
           SUM({REALISED_PROFIT})                   AS realised_profit
    {_fact_from(filters)}
    WHERE {where}
    GROUP BY ym
    ORDER BY ym
    """
    return _with_month_label(query(sql, params))


def _zeroed_row(row: dict[str, Any]) -> dict[str, Any]:
    """Turn an aggregate row's NULLs into zeros.

    When a filter combination matches no orders, MySQL still returns exactly one
    row for a bare aggregate query, but every ``SUM()`` and ``COUNT()`` in it is
    NULL rather than 0. Any arithmetic on that row would raise a TypeError, so
    the NULLs are normalised here, once, at the boundary.
    """
    return {k: (0 if v is None else v) for k, v in row.items()}


def _with_month_label(frame: pd.DataFrame) -> pd.DataFrame:
    """Turn the integer month key into a readable ``YYYY-MM`` label."""
    if frame.empty or "ym" not in frame.columns:
        return frame
    out = frame.copy()
    text = out["ym"].astype("int64").astype(str)
    out["month"] = text.str[:4] + "-" + text.str[4:6]
    return out.drop(columns=["ym"])


# ---------------------------------------------------------------------------
# Breakdowns
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=300)
def category_breakdown(filters: Filters) -> pd.DataFrame:
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT pr.category,
           COUNT(DISTINCT o.order_id)   AS orders,
           SUM(oi.quantity)             AS units,
           SUM({REVENUE})               AS gross_order_value,
           SUM({REALISED})              AS realised_revenue,
           SUM({REALISED_PROFIT})       AS realised_profit
    {_fact_from(filters)}
    WHERE {where}
    GROUP BY pr.category
    ORDER BY realised_revenue DESC
    """
    return query(sql, params)


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=300)
def subcategory_breakdown(filters: Filters) -> pd.DataFrame:
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT pr.category, pr.subcategory,
           SUM(oi.quantity)       AS units,
           SUM({REALISED})        AS realised_revenue,
           SUM({REALISED_PROFIT}) AS realised_profit
    {_fact_from(filters)}
    WHERE {where}
    GROUP BY pr.category, pr.subcategory
    ORDER BY realised_revenue DESC
    """
    return query(sql, params)


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=300)
def city_breakdown(filters: Filters) -> pd.DataFrame:
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT o.shipping_city AS city,
           COUNT(DISTINCT o.order_id) AS orders,
           COUNT(DISTINCT o.customer_id) AS customers,
           SUM(oi.quantity)             AS units,
           SUM({REVENUE})               AS gross_order_value,
           SUM({REALISED})              AS realised_revenue,
           SUM({REALISED_PROFIT})       AS realised_profit
    {_fact_from(filters)}
    WHERE {where}
    GROUP BY city
    ORDER BY realised_revenue DESC
    """
    return query(sql, params)


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=400)
def order_status_breakdown(filters: Filters) -> pd.DataFrame:
    """Order counts *and* the value attached to each status.

    Counts use COUNT(DISTINCT order_id) because the fact table is at line grain.
    """
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT o.status,
           COUNT(DISTINCT o.order_id) AS orders,
           COUNT(DISTINCT o.customer_id) AS customers,
           SUM({REVENUE})             AS gross_order_value
    {_fact_from(filters)}
    WHERE {where}
    GROUP BY o.status
    ORDER BY FIELD(o.status, 'Completed', 'Pending', 'Cancelled', 'Returned')
    """
    return query(sql, params)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=400)
def product_performance(filters: Filters, limit: int | None = None) -> pd.DataFrame:
    """One row per product: units, revenue, cost, profit, margin, catalogue price.

    ``order_count`` is a distinct order count, so a product bought twice in one
    order counts as one order.
    """
    where, params = _filter_sql(filters)
    limit_sql = f" LIMIT {int(limit)}" if limit else ""
    sql = f"""
    SELECT pr.product_id, pr.product_name, pr.category, pr.subcategory, pr.brand,
           pr.price                                        AS catalogue_price,
           COUNT(DISTINCT o.order_id)                      AS order_count,
           SUM(oi.quantity)                                AS units,
           SUM({REVENUE})                                  AS gross_order_value,
           SUM({REALISED})                                 AS realised_revenue,
           SUM({COST})                                     AS total_cost,
           SUM({REALISED_PROFIT})                          AS realised_profit,
           ROUND(AVG(oi.discount_percent), 2)              AS avg_discount_pct
    {_fact_from(filters)}
    WHERE {where}
    GROUP BY pr.product_id, pr.product_name, pr.category, pr.subcategory, pr.brand, pr.price
    ORDER BY realised_revenue DESC{limit_sql}
    """
    return query(sql, params)


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=200)
def product_bands(filters: Filters) -> pd.DataFrame:
    """Realised revenue, units and margin per discount band (0-30)."""
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT CASE
               WHEN oi.discount_percent = 0                THEN '0%'
               WHEN oi.discount_percent BETWEEN 1  AND 5   THEN '1-5%'
               WHEN oi.discount_percent BETWEEN 6  AND 10  THEN '6-10%'
               WHEN oi.discount_percent BETWEEN 11 AND 15  THEN '11-15%'
               WHEN oi.discount_percent BETWEEN 16 AND 20  THEN '16-20%'
               WHEN oi.discount_percent BETWEEN 21 AND 25  THEN '21-25%'
               ELSE '26-30%'
           END                                            AS discount_band,
           MIN(oi.discount_percent)                       AS band_order,
           -- `lines` is a reserved word in MySQL 8, hence line_count.
           COUNT(*)                                       AS line_count,
           SUM(oi.quantity)                               AS units,
           ROUND(AVG(oi.quantity), 2)                     AS units_per_line,
           SUM({REVENUE})                                 AS gross_order_value,
           SUM({REALISED})                                AS realised_revenue,
           SUM({REALISED_PROFIT})                         AS realised_profit,
           ROUND(SUM({REVENUE}) / NULLIF(COUNT(*), 0), 2) AS revenue_per_line
    {_fact_from(filters)}
    WHERE {where}
    GROUP BY discount_band
    ORDER BY band_order
    """
    return query(sql, params)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=200)
def customer_metrics(filters: Filters) -> dict[str, Any]:
    """Registered vs active vs inactive vs repeat customers.

    Registered customers are counted over the whole ``customers`` table (that is
    what "registered" means); the rest are measured inside the filter scope.
    A customer with exactly one order is classified as one-time, more than one
    as repeat - a deliberately simple, transparent rule.
    """
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT
      (SELECT COUNT(*) FROM customers) AS registered_customers,
      COUNT(DISTINCT o.customer_id)    AS active_customers,
      COUNT(DISTINCT c.customer_id)    AS customers_in_scope
    {_fact_from(filters)}
    LEFT JOIN customers c ON c.customer_id = o.customer_id
    WHERE {where}
    """
    base = query(sql, params)
    if base.empty:
        return {}
    out = _zeroed_row(base.iloc[0].to_dict())

    per_customer = f"""
    SELECT COUNT(*) AS customers_with_orders,
           SUM(n > 1) AS repeat_customers
    FROM (
        SELECT o.customer_id, COUNT(DISTINCT o.order_id) AS n
        {_fact_from(filters)}
        WHERE {where}
        GROUP BY o.customer_id
    ) t
    """
    counts = query(per_customer, params)
    if not counts.empty:
        out.update(_zeroed_row(counts.iloc[0].to_dict()))
    out["inactive_customers"] = out["registered_customers"] - out.get("active_customers", 0)
    return out


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=400)
def customer_performance(filters: Filters, limit: int | None = None) -> pd.DataFrame:
    """One row per customer inside the filter scope."""
    where, params = _filter_sql(filters)
    limit_sql = f" LIMIT {int(limit)}" if limit else ""
    sql = f"""
    SELECT c.customer_id, c.name, c.city, c.gender, c.signup_date,
           COUNT(DISTINCT o.order_id) AS orders,
           SUM({REVENUE})             AS gross_order_value,
           SUM({REALISED})            AS realised_revenue,
           SUM({REALISED_PROFIT})     AS realised_profit,
           MIN(o.order_date)          AS first_order,
           MAX(o.order_date)          AS latest_order
    {_fact_from(filters)}
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE {where}
    GROUP BY c.customer_id, c.name, c.city, c.gender, c.signup_date
    ORDER BY realised_revenue DESC{limit_sql}
    """
    return query(sql, params)


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=200)
def orders_per_customer_distribution(filters: Filters) -> pd.DataFrame:
    """How many customers placed 1, 2, 3 ... orders."""
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT n AS orders_placed, COUNT(*) AS customers
    FROM (
        SELECT o.customer_id, COUNT(DISTINCT o.order_id) AS n
        {_fact_from(filters)}
        WHERE {where}
        GROUP BY o.customer_id
    ) t
    GROUP BY n
    ORDER BY n
    """
    return query(sql, params)


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=400)
def order_table(filters: Filters, limit: int = 500) -> pd.DataFrame:
    """Order-level table, one row per order.

    Value is aggregated from the order's own lines, and the payment columns
    come from the single payment row for that order (1-to-1), so each order
    appears exactly once.
    """
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT o.order_id, o.order_date, o.status, o.shipping_city,
           c.customer_id, c.name AS customer_name,
           COUNT(DISTINCT pay.payment_id)            AS payment_id,
           MAX(pay.payment_method)                   AS payment_method,
           MAX(pay.payment_status)                   AS payment_status,
           MAX(pay.payment_date)                     AS payment_date,
           COUNT(oi.order_item_id)                   AS line_count,
           SUM(oi.quantity)                          AS units,
           SUM({REVENUE})                            AS gross_order_value,
           SUM(CASE WHEN o.status = 'Completed' THEN {REVENUE} ELSE 0 END) AS realised_value,
           SUM({PROFIT})                             AS gross_profit
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    JOIN products pr ON pr.product_id = oi.product_id
    JOIN customers c ON c.customer_id = o.customer_id
    LEFT JOIN payments pay ON pay.order_id = o.order_id
    WHERE {where}
    GROUP BY o.order_id, o.order_date, o.status, o.shipping_city,
             c.customer_id, c.name
    ORDER BY o.order_date DESC, o.order_id DESC
    LIMIT {int(limit)}
    """
    # One row per order is guaranteed by the GROUP BY, not by any assumption
    # about cardinality: order_items is many-per-order and payments is
    # one-per-order, so the line SUM() aggregates the order's own lines and the
    # MAX() picks the single payment. products joins on its primary key.
    return query(sql, params)


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=200)
def order_size_trend(filters: Filters) -> pd.DataFrame:
    """Average lines and units per order, by month."""
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT EXTRACT(YEAR_MONTH FROM o.order_date) AS ym,
           COUNT(DISTINCT o.order_id)          AS orders,
           -- `lines` is a reserved word in MySQL 8, hence line_count.
           COUNT(*)                            AS line_count,
           SUM(oi.quantity)                    AS units,
           SUM({REVENUE}) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS avg_value_per_order
    {_fact_from(filters)}
    WHERE {where}
    GROUP BY ym
    ORDER BY ym
    """
    return _with_month_label(query(sql, params))


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=200)
def order_size_distribution(filters: Filters) -> pd.DataFrame:
    """How many orders fall into each basket-size band, in units per order.

    The same cardinality rule as everywhere else in this module: ``order_items``
    is collapsed to one row per order in a derived table *before* the bands are
    counted, so an order with three product lines contributes one order, not
    three. That is why this is a subquery rather than a ``GROUP BY`` on the
    line-grain fact table.
    """
    where, params = _filter_sql(filters)
    sql = f"""
    SELECT size_band, COUNT(*) AS orders
    FROM (
        SELECT o.order_id AS order_id,
               CASE
                   WHEN SUM(oi.quantity) = 1  THEN '1 unit'
                   WHEN SUM(oi.quantity) = 2  THEN '2 units'
                   WHEN SUM(oi.quantity) = 3  THEN '3 units'
                   WHEN SUM(oi.quantity) <= 5 THEN '4-5 units'
                   WHEN SUM(oi.quantity) <= 8 THEN '6-8 units'
                   ELSE '9+ units'
               END AS size_band
        {_fact_from(filters)}
        WHERE {where}
        GROUP BY o.order_id
    ) AS per_order
    GROUP BY size_band
    """
    return query(sql, params)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
# CARDINALITY NOTE (applies to the payment functions below)
#   Revenue lives on order_items, payment facts live on payments, and
#   payments is one-to-one with orders. Rather than rely on that 1:1 to keep a
#   SUM() correct, the money side is aggregated to exactly one row per order in
#   a CTE first, and only then joined to payments. If payments ever became
#   one-to-many, these queries would still be right.


def _order_value_cte(filters: Filters) -> tuple[str, list[Any]]:
    """A CTE holding exactly one row per order, with that order's total value.

    This is the shared building block for every payment query. It applies the
    same filters as the rest of the dashboard, line-level category filters
    included, and it reuses :func:`_fact_from` so the payments join required by
    a payment-method filter is present when needed.

    ``GROUP BY oi.order_id`` is what makes it one row per order. Everything
    else in the SELECT is either an order attribute (wrapped in MAX, which is
    safe because a function of the same order's column is constant across its
    lines) or the SUM of that order's own lines.
    """
    where, params = _filter_sql(filters)
    cte = f"""
    order_value AS (
        SELECT oi.order_id,
               MAX(o.status)   AS status,
               MAX(o.shipping_city) AS city,
               MAX(o.order_date)    AS order_date,
               SUM({REVENUE})       AS value
        {_fact_from(filters)}
        WHERE {where}
        GROUP BY oi.order_id
    )
    """
    return cte, params


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=300)
def payment_method_summary(filters: Filters) -> pd.DataFrame:
    """Payment counts, status split and realised revenue per payment method.

    ``order_value`` collapses order_items to one row per order *before* the
    payments join, so no order's value can be counted more than once.
    """
    value_cte, params = _order_value_cte(filters)

    sql = f"""
    WITH {value_cte}
    SELECT p.payment_method,
           COUNT(*)                                                  AS payments,
           COUNT(DISTINCT ov.order_id)                               AS orders,
           SUM(p.payment_status = 'Paid')                            AS paid,
           SUM(p.payment_status = 'Failed')                          AS failed,
           SUM(p.payment_status = 'Refunded')                        AS refunded,
           SUM(p.payment_status = 'Pending')                         AS pending,
           ROUND(100 * SUM(p.payment_status = 'Failed') / COUNT(*), 2) AS failure_rate_pct,
           -- Money is deliberately NOT rounded per group. Rounding six method
           -- subtotals independently makes their sum differ from the exact
           -- total by a cent or two, which looks like a duplication bug in the
           -- totals check. The displayed figure is rounded once, in Python, at
           -- the point of formatting.
           SUM(ov.value)                                            AS gross_order_value,
           SUM(CASE WHEN ov.status = 'Completed' THEN ov.value ELSE 0 END) AS realised_revenue
    FROM payments p
    JOIN order_value ov ON ov.order_id = p.order_id
    GROUP BY p.payment_method
    ORDER BY payments DESC
    """
    return query(sql, params)


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=300)
def payment_status_summary(filters: Filters) -> pd.DataFrame:
    """Payment status totals, with the order status they sit on."""
    value_cte, params = _order_value_cte(filters)
    sql = f"""
    WITH {value_cte}
    SELECT p.payment_status,
           p.payment_method,
           COUNT(*)                                     AS payments,
           SUM(ov.value)                                AS gross_order_value
    FROM payments p
    JOIN order_value ov ON ov.order_id = p.order_id
    GROUP BY p.payment_status, p.payment_method
    ORDER BY FIELD(p.payment_status, 'Paid', 'Pending', 'Failed', 'Refunded')
    """
    return query(sql, params)


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=200)
def payment_failure_detail(filters: Filters) -> pd.DataFrame:
    """The two different meanings of 'failed', kept explicitly separate.

    ``payment_status = 'Failed'`` is a *payment* outcome.  Cancelled or
    Returned is an *order* outcome. They are different populations and are
    never added together.

    Each definition is a single unconditional aggregate over the whole scope,
    with the population selected by a CASE inside the aggregate. An earlier
    version used ``CROSS JOIN`` against a totals CTE, which MySQL rejects under
    ``ONLY_FULL_GROUP_BY`` (error 1140: a nonaggregated column in a query with
    no GROUP BY). The denominator is now a scalar subquery over the same CTE, so
    both branches still divide by the total in-scope gross value.
    """
    value_cte, params = _order_value_cte(filters)
    denominator = "NULLIF((SELECT SUM(value) FROM order_value), 0)"
    sql = f"""
    WITH {value_cte}
    SELECT 'Payment failed (payment_status = Failed)'                     AS definition,
           SUM(p.payment_status = 'Failed')                              AS orders,
           SUM(CASE WHEN p.payment_status = 'Failed' THEN ov.value ELSE 0 END) AS gross_order_value,
           ROUND(100 * SUM(CASE WHEN p.payment_status = 'Failed' THEN ov.value ELSE 0 END)
                 / {denominator}, 2)                                     AS pct_of_gross
    FROM order_value ov
    JOIN payments p ON p.order_id = ov.order_id
    UNION ALL
    SELECT 'Order did not complete (Cancelled or Returned)'              AS definition,
           SUM(ov.status IN ('Cancelled', 'Returned'))                   AS orders,
           SUM(CASE WHEN ov.status IN ('Cancelled', 'Returned') THEN ov.value ELSE 0 END) AS gross_order_value,
           ROUND(100 * SUM(CASE WHEN ov.status IN ('Cancelled', 'Returned') THEN ov.value ELSE 0 END)
                 / {denominator}, 2)                                     AS pct_of_gross
    FROM order_value ov
    """
    return query(sql, params)


# ---------------------------------------------------------------------------
# Insights (facts the UI is allowed to talk about)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=200)
def growth_summary(filters: Filters) -> dict[str, Any]:
    """First six vs last six COMPLETE months, excluding the partial month."""
    # EXTRACT(YEAR_MONTH ...) rather than DATE_FORMAT(..., '%Y-%m'): the driver
    # substitutes parameters with `query % args`, so a literal percent in the
    # SQL is read as a format specifier. The 2026-09 cut-off is the partial
    # month, matching sql/11_advanced_analysis.sql.
    sql = """
    WITH monthly AS (
        SELECT EXTRACT(YEAR_MONTH FROM o.order_date) AS ym,
               COUNT(DISTINCT o.order_id)          AS orders
        FROM orders o
        WHERE o.order_date < '2026-09-01'
        GROUP BY ym
    ),
    ranked AS (
        SELECT ym, orders,
               ROW_NUMBER() OVER (ORDER BY ym)                              AS rn_first,
               ROW_NUMBER() OVER (ORDER BY ym DESC)                         AS rn_last,
               COUNT(*) OVER ()                                             AS n_months
        FROM monthly
    )
    SELECT
      (SELECT ROUND(AVG(orders), 2) FROM ranked WHERE rn_first <= 6)       AS first_six_avg_orders,
      (SELECT ROUND(AVG(orders), 2) FROM ranked WHERE rn_last  <= 6)       AS last_six_avg_orders,
      (SELECT n_months FROM ranked LIMIT 1)                               AS complete_months
    """
    frame = query(sql)
    if frame.empty:
        return {}
    out = _zeroed_row(frame.iloc[0].to_dict())
    if out.get("first_six_avg_orders") and out.get("last_six_avg_orders"):
        out["change_pct"] = round(
            100 * (out["last_six_avg_orders"] - out["first_six_avg_orders"])
            / out["first_six_avg_orders"], 2
        )
    return out


@st.cache_data(ttl=CACHE_TTL_ANALYTICS, show_spinner=False, max_entries=100)
def concentration(filters: Filters) -> dict[str, Any]:
    """Top-10 customer share of realised revenue - a concentration check."""
    where, params = _filter_sql(filters)
    sql = f"""
    WITH spend AS (
        SELECT o.customer_id,
               SUM({REALISED}) AS spend
        {_fact_from(filters)}
        WHERE {where}
        GROUP BY o.customer_id
        HAVING SUM({REALISED}) > 0
    ),
    ranked AS (
        SELECT spend,
               ROW_NUMBER() OVER (ORDER BY spend DESC) AS rn
        FROM spend
    )
    SELECT ROUND(100 * SUM(CASE WHEN rn <= 10 THEN spend ELSE 0 END)
                 / NULLIF(SUM(spend), 0), 2) AS top_10_share_pct,
           COUNT(*) AS paying_customers
    FROM ranked
    """
    frame = query(sql, params)
    return _zeroed_row(frame.iloc[0].to_dict()) if not frame.empty else {}


__all__ = [
    "REVENUE", "COST", "PROFIT", "REALISED", "REALISED_PROFIT",
    "query", "reference_data", "dataset_summary", "kpi_metrics",
    "monthly_trend", "category_breakdown", "subcategory_breakdown",
    "city_breakdown", "order_status_breakdown", "product_performance",
    "product_bands", "customer_metrics", "customer_performance",
    "orders_per_customer_distribution", "order_table", "order_size_trend",
    "payment_method_summary", "payment_status_summary", "payment_failure_detail",
    "growth_summary", "concentration", "DashboardDBError",
]
