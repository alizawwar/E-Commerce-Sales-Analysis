"""Operations / Orders - order flow, basket size and the order-level record set.

The four order statuses are given separate treatment throughout: each has its
own colour, its own card and its own place in the status mix, because
"cancelled" and "returned" are not interchangeable with "pending".
"""

from __future__ import annotations

import streamlit as st

from .. import charts, queries
from ..components import (
    Kpi,
    callout,
    chart,
    data_table,
    kpi_grid,
    panel,
    section,
)
from ..config import PALETTE, STATUS_COLORS
from ..metrics import build_metric_bundle, share_pct
from ..utils import Filters, fmt_int, fmt_pct, fmt_pkr, fmt_ratio

ROW_OPTIONS = {
    "500 most recent": 500,
    "2,000 most recent": 2000,
    "5,000 most recent": 5000,
    "All matching orders": 20000,
}


def render(filters: Filters) -> None:
    kpi = queries.kpi_metrics(filters)
    if not kpi:
        st.warning("No orders match the current filters.")
        return
    m = build_metric_bundle(kpi)
    status = queries.order_status_breakdown(filters)

    # ----------------------------------------------- 1. the four statuses
    section("Order flow", "Each status counted once per order, never once per line")
    kpi_grid(
        [
            Kpi("Total orders", fmt_int(m["total_orders"]),
                "Distinct orders in the current scope", PALETTE["neutral"]),
            Kpi("Completed", fmt_int(m["completed_orders"]),
                f"{fmt_pct(m['completion_rate'])} of orders",
                STATUS_COLORS["Completed"]),
            Kpi("Pending", fmt_int(m["pending_orders"]),
                f"{fmt_pct(m['pending_rate'])} - still in flight",
                STATUS_COLORS["Pending"]),
            Kpi("Cancelled", fmt_int(m["cancelled_orders"]),
                f"{fmt_pct(m['cancellation_rate'])} of orders",
                STATUS_COLORS["Cancelled"]),
            Kpi("Returned", fmt_int(m["returned_orders"]),
                f"{fmt_pct(m['return_rate'])} of orders",
                STATUS_COLORS["Returned"]),
        ]
    )
    callout(
        "<b>Why the counts can exceed 100%.</b> They cannot - each percentage is that "
        "status divided by all orders in scope, so the four shares add to 100%. Order "
        "counts use <code>COUNT(DISTINCT order_id)</code>, because the underlying fact "
        "table has one row per <i>product line</i> and an order with three lines would "
        "otherwise be counted three times.", tag="How to read"
    )

    # ------------------------------------------------- 2. basket economics
    section("Basket and value per order", "Order size and order value, side by side")
    kpi_grid(
        [
            Kpi("Lines per order", fmt_ratio(m["lines_per_order"]),
                "Distinct products on an order", PALETTE["neutral"]),
            Kpi("Units per order", fmt_ratio(m["units_per_order"]),
                "Total quantity on an order", PALETTE["neutral"]),
            Kpi("Average order value", fmt_pkr(m["average_order_value"], 0),
                "Realised / completed order", PALETTE["revenue"]),
            Kpi("Gross value per order", fmt_pkr(
                (m["gross_order_value"] / m["total_orders"]) if m["total_orders"] else 0, 0),
                "Every selected status", PALETTE["neutral"]),
            Kpi("Product lines", fmt_int(m["line_count"]),
                "One row per product on an order", PALETTE["neutral"]),
        ]
    )

    with panel("Orders and completion rate by month",
               "Volume on the left axis, share completed on the right"):
        chart(charts.order_mix_trend(queries.monthly_trend(filters)), "o_mix_trend")

    # ----------------------------------------------------- 3. the breakdown
    section("Status mix and geography", "Where orders come from and how they ended")
    left, right = st.columns([1, 1.15], gap="medium")
    with left:
        with panel("Order status mix", "Share of orders in the current scope"):
            chart(charts.status_distribution(status), "o_status")
    with right:
        with panel("Value attached to each status",
                   "Potential value - Completed is the only realised part"):
            chart(charts.status_value_split(status), "o_status_value")

    city = queries.city_breakdown(filters)
    with panel("Orders by shipping city", "Top 12 cities by order volume"):
        chart(charts.orders_by_city_volume(city, top=12), "o_city")

    # ---------------------------------------------------- 4. order size
    section("Order size", "How many units each order contains")
    size = queries.order_size_distribution(filters)
    left, right = st.columns([1, 1.3], gap="medium")
    with left:
        with panel("Orders per basket-size band", "Units on the order, not product lines"):
            chart(charts.order_size_distribution(size), "o_size_dist")
    with right:
        trend = queries.order_size_trend(filters)
        with panel("Average basket over time", "Units and lines per order, by month"):
            chart(charts.basket_size_trend(trend), "o_basket")

    if not status.empty:
        with panel("Status detail", "Sortable - click any column heading"):
            table = status.copy()
            table["share_pct"] = table.apply(
                lambda r: share_pct(r["orders"], table["orders"].sum()), axis=1
            )
            table["value_share_pct"] = table.apply(
                lambda r: share_pct(r["gross_order_value"],
                                    table["gross_order_value"].sum()), axis=1
            )
            data_table(
                table[["status", "orders", "customers", "gross_order_value",
                       "share_pct", "value_share_pct"]],
                {
                    "status": st.column_config.TextColumn("Status", width="small"),
                    "orders": st.column_config.NumberColumn("Orders", format="%d"),
                    "customers": st.column_config.NumberColumn("Customers", format="%d"),
                    "gross_order_value": st.column_config.NumberColumn("Value (PKR)", format="%.0f"),
                    "share_pct": st.column_config.NumberColumn("Share of orders (%)", format="%.2f"),
                    "value_share_pct": st.column_config.NumberColumn("Share of value (%)", format="%.2f"),
                },
                height=200, key="o_status_table",
            )

    # ------------------------------------------------------ 5. the records
    section("Order records", "One row per order, with its single payment record")
    scope = st.selectbox("How many orders to load", list(ROW_OPTIONS), key="o_limit")
    orders = queries.order_table(filters, limit=ROW_OPTIONS[scope])
    if orders.empty:
        st.info("No orders in the selected scope.")
        return

    st.caption(
        f"Showing {len(orders):,} of {fmt_int(m['total_orders'])} orders in scope. "
        "Search and sorting apply to the rows loaded above."
    )

    search = st.text_input(
        "Search orders",
        placeholder="e.g. an order id, a customer name, a city, a payment method",
        key="o_search",
    )
    table = orders.copy()
    table["avg_order_value"] = table.apply(
        lambda r: (r["gross_order_value"] / r["line_count"]) if r["line_count"] else 0,
        axis=1,
    )
    if search.strip():
        needle = search.strip().lower()
        table = table[
            table["order_id"].astype(str).str.lower().str.contains(needle, na=False)
            | table["customer_name"].str.lower().str.contains(needle, na=False)
            | table["shipping_city"].str.lower().str.contains(needle, na=False)
            | table["payment_method"].str.lower().str.contains(needle, na=False)
            | table["status"].str.lower().str.contains(needle, na=False)
        ]
        st.caption(f"{len(table):,} of {len(orders):,} loaded orders match '{search}'.")

    if table.empty:
        st.info("No orders match that search. Try a shorter term, or load more rows.")
        return

    with panel(f"{len(table):,} orders", "Searchable and sortable"):
        data_table(
            table[["order_id", "order_date", "status", "shipping_city", "customer_id",
                   "customer_name", "line_count", "units", "gross_order_value",
                   "realised_value", "gross_profit", "avg_order_value",
                   "payment_method", "payment_status", "payment_date"]],
            {
                "order_id": st.column_config.TextColumn("Order", width="medium"),
                "order_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "status": st.column_config.TextColumn("Order status", width="small"),
                "shipping_city": st.column_config.TextColumn("City", width="small"),
                "customer_id": st.column_config.TextColumn("Customer", width="small"),
                "customer_name": st.column_config.TextColumn("Name", width="medium"),
                "line_count": st.column_config.NumberColumn("Lines", format="%d"),
                "units": st.column_config.NumberColumn("Units", format="%d"),
                "gross_order_value": st.column_config.NumberColumn("Order value (PKR)", format="%.0f"),
                "realised_value": st.column_config.NumberColumn("Realised (PKR)", format="%.0f"),
                "gross_profit": st.column_config.NumberColumn("Profit (PKR)", format="%.0f"),
                "avg_order_value": st.column_config.NumberColumn("Value per line (PKR)", format="%.0f"),
                "payment_method": st.column_config.TextColumn("Payment method", width="small"),
                "payment_status": st.column_config.TextColumn("Payment status", width="small"),
                "payment_date": st.column_config.DateColumn("Paid on", format="YYYY-MM-DD"),
            },
            height=520, key="o_detail_table",
        )

    callout(
        "<b>Two different status columns.</b> <code>status</code> is the order's own "
        "state - Completed, Pending, Cancelled, Returned. <code>payment_status</code> "
        "is the outcome of the single payment row for that order - Paid, Pending, "
        "Failed, Refunded. A Completed order can carry a Refunded payment, and it "
        "does in this dataset. The two columns are never combined into one figure.",
        tag="Order status vs payment status",
    )
