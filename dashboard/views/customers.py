"""Customers - reach, repeat behaviour, spend concentration and segmentation.

The page is ordered by the questions a retention question would ask: how many
people are here, do they come back, where does the money sit, and how
concentrated is it.
"""

from __future__ import annotations

import streamlit as st

from .. import charts, queries
from ..components import (
    Kpi,
    bullets,
    callout,
    chart,
    data_table,
    kpi_grid,
    panel,
    section,
)
from ..config import PALETTE
from ..metrics import build_metric_bundle, customer_segment, share_pct
from ..utils import (
    Filters,
    fmt_int,
    fmt_pct,
    fmt_pkr,
    fmt_pkr_compact,
    safe_div,
)

SEGMENT_NOTE = (
    "<b>Segmentation rule, stated plainly.</b> A customer with exactly one order "
    "in scope is <b>One-time</b>; more than one order is <b>Repeat</b>. That is a "
    "rule, not a model - it is reproducible, and anyone can check it against the "
    "customer table."
)


def render(filters: Filters) -> None:
    cm = queries.customer_metrics(filters)
    if not cm:
        st.warning("No customers match the current filters.")
        return

    customers = queries.customer_performance(filters)
    kpi = queries.kpi_metrics(filters)
    m = build_metric_bundle(kpi) if kpi else {}

    registered = cm.get("registered_customers") or 0
    active = cm.get("active_customers") or 0
    inactive = cm.get("inactive_customers") or 0
    repeat = cm.get("repeat_customers") or 0
    repeat_rate = safe_div(100 * repeat, active)

    # ------------------------------------------------------- 1. reach
    section("Reach and retention", "Measured inside the current filter scope")
    kpi_grid(
        [
            Kpi("Registered customers", fmt_int(registered),
                "Total in the customers table", PALETTE["neutral"]),
            Kpi("Active customers", fmt_int(active),
                "At least one order in scope", PALETTE["revenue"]),
            Kpi("Inactive customers", fmt_int(inactive),
                f"{fmt_pct(safe_div(100 * inactive, registered))} never ordered",
                PALETTE["warning"]),
            Kpi("Repeat customers", fmt_int(repeat),
                "More than one order in scope", PALETTE["success"]),
            Kpi("Repeat customer rate", fmt_pct(repeat_rate),
                "Repeat / active customers", PALETTE["success"]),
        ]
    )
    callout(SEGMENT_NOTE, tag="Definition")

    # ------------------------------------------- 2. segmentation in money
    if not customers.empty:
        customers = customers.copy()
        customers["segment"] = [customer_segment(n) for n in customers["orders"]]
        segments = (
            customers.groupby("segment")
            .agg(customers=("customer_id", "nunique"),
                 revenue=("realised_revenue", "sum"),
                 orders=("orders", "sum"))
            .reindex(["One-time", "Repeat"])
            .fillna(0)
            .reset_index()
        )

        section("Segmentation", "One-time versus repeat, by count and by money")
        left, right = st.columns([1, 1.15], gap="medium")
        with left:
            with panel("One-time versus repeat customers", "Count and realised revenue"):
                chart(charts.segment_mix(segments), "cu_segment")
        with right:
            with panel("Orders placed per customer", "The long tail is bucketed at 11+"):
                distribution = queries.orders_per_customer_distribution(filters)
                chart(charts.orders_per_customer(distribution), "cu_orders_dist")

            concentration = queries.concentration(filters)
            if concentration:
                share = concentration.get("top_10_share_pct")
                kpi_grid(
                    [
                        Kpi("Top 10 customers' share of realised revenue",
                            fmt_pct(share),
                            f"Out of {fmt_int(concentration.get('paying_customers', 0))} "
                            "customers with realised spend", PALETTE["warning"]),
                        Kpi("Revenue per active customer",
                            fmt_pkr(safe_div(m.get("realised_revenue", 0), active) or 0, 0),
                            "Realised revenue / active customer", PALETTE["revenue"]),
                    ]
                )

    # --------------------------------------------------- 3. distribution
    if not customers.empty:
        section("Spend distribution",
                "Every customer in scope as one point: orders against realised spend")
        with panel("Orders against realised revenue, one point per customer",
                   "A tight diagonal means a fairly even spread; a steep one means "
                   "concentration"):
            chart(charts.customer_revenue_scatter(customers), "cu_scatter")

        top = customers.nlargest(10, "realised_revenue").iloc[::-1]
        with panel("Top 10 customers by realised revenue", "Hover for city and order count"):
            chart(charts.top_customers(customers, top=10), "cu_top")

    # ------------------------------------------------- 4. the record set
    section("Customer records", "Search by name or city. Click any column to sort.")
    if customers.empty:
        st.info("No customers in the selected scope.")
        return

    search = st.text_input("Search customers", placeholder="e.g. Ayesha, Karachi",
                           key="cu_search")
    table = customers.copy()
    table["avg_order_value"] = table.apply(
        lambda r: safe_div(r["realised_revenue"], r["orders"]) or 0, axis=1
    )
    if search.strip():
        needle = search.strip().lower()
        table = table[
            table["name"].str.lower().str.contains(needle, na=False)
            | table["city"].str.lower().str.contains(needle, na=False)
        ]
        st.caption(f"{len(table):,} of {len(customers):,} customers match '{search}'.")

    if table.empty:
        st.info("No customers match that search. Try a shorter term.")
        return

    with panel(f"All {len(table):,} matching customers", "Searchable and sortable"):
        data_table(
            table[["customer_id", "name", "city", "gender", "signup_date", "segment",
                   "orders", "gross_order_value", "realised_revenue", "realised_profit",
                   "avg_order_value", "first_order", "latest_order"]],
            {
                "customer_id": st.column_config.TextColumn("ID", width="small"),
                "name": st.column_config.TextColumn("Name", width="medium"),
                "city": st.column_config.TextColumn("City", width="small"),
                "gender": st.column_config.TextColumn("Gender", width="small"),
                "signup_date": st.column_config.DateColumn("Signed up", format="YYYY-MM-DD"),
                "segment": st.column_config.TextColumn("Segment", width="small"),
                "orders": st.column_config.NumberColumn("Orders", format="%d"),
                "gross_order_value": st.column_config.NumberColumn("Gross value (PKR)", format="%.0f"),
                "realised_revenue": st.column_config.NumberColumn("Realised revenue (PKR)", format="%.0f"),
                "realised_profit": st.column_config.NumberColumn("Realised profit (PKR)", format="%.0f"),
                "avg_order_value": st.column_config.NumberColumn("Avg order value (PKR)", format="%.0f"),
                "first_order": st.column_config.DateColumn("First order", format="YYYY-MM-DD"),
                "latest_order": st.column_config.DateColumn("Latest order", format="YYYY-MM-DD"),
            },
            height=520, key="cu_detail_table",
        )

    bullets(
        [
            "<b>Registered</b> counts the whole <code>customers</code> table, so it does "
            "not move when the filters move. <b>Active</b> counts distinct "
            "<code>customer_id</code> inside the filtered orders.",
            "<b>Inactive</b> is registered minus active. With a narrow date range a "
            "customer who ordered last year is counted as inactive here - that is a "
            "consequence of the filter, not a data problem.",
            "<b>Realised revenue</b> counts Completed orders only, on the same basis as "
            "every other page.",
            f"<b>{fmt_pkr_compact(m.get('realised_revenue', 0))}</b> of realised revenue "
            f"is spread across {fmt_int(active)} active customers in this scope.",
        ]
    )
