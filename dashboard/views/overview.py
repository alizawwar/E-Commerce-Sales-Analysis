"""Overview - the executive dashboard.

One screen that answers "how is the business doing right now, within the
selected filters?". Laid out as a dashboard grid rather than a single column,
top to bottom:

    1. one block of ten headline numbers, five across (money, then volume, then
       order quality) so the whole picture fits in a single glance
    2. the gross-value bridge and its decomposition - what was earned, what was
       lost, what is still in flight
    3. the monthly trend beside the order-status mix, then order volume and
       average order value
    4. revenue contribution by category and by product
    5. where it ships, and how it was paid for
    6. the ranked detail tables behind each of the above

Every figure in those blocks was already on this page before; only the grouping
and the row geometry changed. No metric was added, removed or redefined.

Everything follows the global filters, and the realised / potential distinction
is stated on the page rather than left to the reader's memory.
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
    spacer,
)
from ..config import PALETTE
from ..metrics import build_metric_bundle, share_pct
from ..utils import (
    Filters,
    fmt_int,
    fmt_pct,
    fmt_pkr,
    fmt_pkr_compact,
    fmt_ratio,
)

MONEY_HELP = (
    "<b>Realised</b> counts Completed orders only. <b>Gross / potential</b> "
    "counts every selected status - the value that was attempted, not the "
    "value that was earned."
)


def render(filters: Filters) -> None:
    kpi = queries.kpi_metrics(filters)
    if not kpi:
        st.warning(
            "No orders match the selected filters, so there is nothing to summarise. "
            "Widen the date range or clear a filter."
        )
        return

    m = build_metric_bundle(kpi)

    # ---------------------------------------------------------------- KPIs
    # One block of ten, five across, rather than three stacked bands. Every
    # figure here already existed on this page in Phase 4/5; only the grouping
    # changed. Nothing is new: the band is exactly the same metric set, read
    # left-to-right as money -> volume -> quality, which is the order a reader
    # actually asks the questions in.
    section("Performance at a glance",
            "Realised figures are Completed orders only. Gross value covers every "
            "selected status.")
    kpi_grid(
        [
            Kpi("Realised revenue", fmt_pkr_compact(m["realised_revenue"]),
                "Completed orders only", PALETTE["revenue"]),
            Kpi("Realised profit", fmt_pkr_compact(m["realised_profit"]),
                "Revenue less product cost", PALETTE["profit"]),
            Kpi("Profit margin",
                fmt_pct(m["margin_pct"]) if m["margin_pct"] is not None else "-",
                f"On {fmt_pkr_compact(m['realised_revenue'])} realised",
                PALETTE["profit"]),
            Kpi("Total orders", fmt_int(m["total_orders"]),
                f"{fmt_int(m['completed_orders'])} completed", PALETTE["neutral"]),
            Kpi("Active customers", fmt_int(m["active_customers"]),
                "Placed at least one order in scope", PALETTE["revenue"]),
            Kpi("Average order value", fmt_pkr(m["average_order_value"], 0),
                "Realised / completed order", PALETTE["revenue"]),
            Kpi("Completed orders", fmt_int(m["completed_orders"]),
                f"{fmt_pct(m['completion_rate'])} of all orders",
                PALETTE["success"]),
            Kpi("Units sold", fmt_int(m["units_total"]),
                f"{fmt_ratio(m['units_per_order'])} per order", PALETTE["neutral"]),
            Kpi("Return rate", fmt_pct(m["return_rate"]),
                f"{fmt_int(m['returned_orders'])} orders returned", PALETTE["returned"]),
            Kpi("Cancellation rate", fmt_pct(m["cancellation_rate"]),
                f"{fmt_int(m['cancelled_orders'])} orders cancelled", PALETTE["danger"]),
        ],
        columns=5,
    )

    # ------------------------------------------------- revenue vs potential
    section("Value, and where it went", "Two quantities kept deliberately apart")
    kpi_grid(
        [
            Kpi("Gross / potential value", fmt_pkr_compact(m["gross_order_value"]),
                "Every selected status", PALETTE["neutral"]),
            Kpi("Realised share of gross", fmt_pct(m["realised_share_pct"]),
                "Realised / gross", PALETTE["success"]),
            Kpi("Value not completed", fmt_pkr_compact(m["value_not_completed"]),
                f"Cancelled + returned, {fmt_pct(m['not_completed_pct'])} of gross",
                PALETTE["danger"]),
            Kpi("Value still pending", fmt_pkr_compact(m["value_pending"]),
                f"{fmt_pct(m['pending_pct'])} of gross - in flight, not lost",
                PALETTE["warning"]),
            Kpi("Discount given away", fmt_pkr_compact(m["discount_value_realised"]),
                f"{fmt_pct(m['discounted_line_share_pct'])} of lines discounted",
                PALETTE["warning"]),
        ]
    )

    trend = queries.monthly_trend(filters)
    status = queries.order_status_breakdown(filters)

    with panel("Where gross order value went",
               "One bar, three parts: realised, lost and still pending"):
        chart(charts.value_bridge(
            m["realised_revenue"], m["value_not_completed"], m["value_pending"]
        ), "ov_bridge", height=124)

    callout(MONEY_HELP + " The bridge above is the identity that keeps them "
            "separate: realised + not completed + pending = gross.", tag="How to read")

    # -------------------------------------------------------------- trends
    section("Revenue, orders and status", "Monthly trend against the status mix")
    trend_col, status_col = st.columns([1.62, 1.0], gap="medium")
    with trend_col:
        with panel("Realised revenue and profit by month", "Completed orders only"):
            chart(charts.revenue_profit_trend(trend), "ov_trend")
    with status_col:
        with panel("Order status mix", "Share of orders in the current scope"):
            chart(charts.status_distribution(status), "ov_status")

    left, right = st.columns(2, gap="medium")
    with left:
        with panel("Order volume by month", "All selected statuses, completed overlaid"):
            chart(charts.order_volume_trend(trend), "ov_volume")
    with right:
        with panel("Average order value by month", "Realised revenue / completed orders"):
            chart(charts.aov_trend(trend), "ov_aov")

    callout(
        "2026-09 is a <b>partial month</b> - the dataset ends on 2026-09-26 - so the "
        "last point on every trend is not comparable with the months before it. "
        "Month-over-month comparisons elsewhere in the dashboard exclude it.",
        tag="Partial month",
    )

    # ---------------------------------------------------------- breakdowns
    category = queries.category_breakdown(filters)
    city = queries.city_breakdown(filters)

    section("Revenue contribution", "Where the money comes from")
    # Category names are one or two words; product names are not. The row is
    # deliberately uneven so the product list gets a label column wide enough
    # to read instead of pushing the bars into a sliver.
    left, right = st.columns([0.82, 1.18], gap="medium")
    with left:
        with panel("Revenue and profit by category", "Top 10 by realised revenue"):
            chart(charts.category_performance(category, top=10), "ov_category")
    with right:
        products = queries.product_performance(filters, limit=10)
        with panel("Top products by realised revenue", "The 10 largest earners"):
            chart(charts.top_products(products, "realised_revenue", top=10), "ov_products")

    section("Where it ships, and how it was paid for", "Geography and payment method")
    left, right = st.columns(2, gap="medium")
    with left:
        with panel("Revenue by shipping city", "Top 12 cities, leader highlighted"):
            chart(charts.city_revenue(city, top=12), "ov_city")
    with right:
        methods = queries.payment_method_summary(filters)
        with panel("Payment methods", "Share of payments in scope"):
            chart(charts.payment_method_usage(methods), "ov_pay")

    # ------------------------------------------------------ detail tables
    spacer(6)
    section("Ranked detail", "The tables behind the charts above, adjusted to the filters")
    tab_cat, tab_prod, tab_city = st.tabs(["Categories", "Products", "Cities"])

    with tab_cat:
        if category.empty:
            st.info("No category data for the selected filters.")
        else:
            table = category.head(10).copy()
            total_revenue = table["realised_revenue"].sum() or 1
            table["share_pct"] = table.apply(
                lambda r: share_pct(r["realised_revenue"], total_revenue), axis=1
            )
            table["margin_pct"] = table.apply(
                lambda r: share_pct(r["realised_profit"], r["realised_revenue"]), axis=1
            )
            data_table(
                table[["category", "orders", "units", "realised_revenue",
                       "realised_profit", "margin_pct", "share_pct"]],
                {
                    "category": st.column_config.TextColumn("Category", width="medium"),
                    "orders": st.column_config.NumberColumn("Orders", format="%d"),
                    "units": st.column_config.NumberColumn("Units", format="%d"),
                    "realised_revenue": st.column_config.NumberColumn("Revenue (PKR)", format="%.0f"),
                    "realised_profit": st.column_config.NumberColumn("Profit (PKR)", format="%.0f"),
                    "margin_pct": st.column_config.NumberColumn("Margin (%)", format="%.2f"),
                    "share_pct": st.column_config.NumberColumn("Share (%)", format="%.2f"),
                },
                height=400, key="ov_cat_table",
            )

    with tab_prod:
        if products.empty:
            st.info("No product data for the selected filters.")
        else:
            show = products.copy()
            show["margin_pct"] = show.apply(
                lambda r: share_pct(r["realised_profit"], r["realised_revenue"]), axis=1
            )
            data_table(
                show[["product_name", "category", "units", "order_count",
                      "realised_revenue", "realised_profit", "margin_pct"]],
                {
                    "product_name": st.column_config.TextColumn("Product", width="large"),
                    "category": st.column_config.TextColumn("Category"),
                    "units": st.column_config.NumberColumn("Units", format="%d"),
                    "order_count": st.column_config.NumberColumn("Orders", format="%d"),
                    "realised_revenue": st.column_config.NumberColumn("Revenue (PKR)", format="%.0f"),
                    "realised_profit": st.column_config.NumberColumn("Profit (PKR)", format="%.0f"),
                    "margin_pct": st.column_config.NumberColumn("Margin (%)", format="%.2f"),
                },
                height=400, key="ov_prod_table",
            )

    with tab_city:
        if city.empty:
            st.info("No city data for the selected filters.")
        else:
            table = city.head(15).copy()
            total_revenue = table["realised_revenue"].sum() or 1
            table["share_pct"] = table.apply(
                lambda r: share_pct(r["realised_revenue"], total_revenue), axis=1
            )
            data_table(
                table[["city", "orders", "customers", "units", "realised_revenue",
                       "realised_profit", "share_pct"]],
                {
                    "city": st.column_config.TextColumn("City", width="medium"),
                    "orders": st.column_config.NumberColumn("Orders", format="%d"),
                    "customers": st.column_config.NumberColumn("Customers", format="%d"),
                    "units": st.column_config.NumberColumn("Units", format="%d"),
                    "realised_revenue": st.column_config.NumberColumn("Revenue (PKR)", format="%.0f"),
                    "realised_profit": st.column_config.NumberColumn("Profit (PKR)", format="%.0f"),
                    "share_pct": st.column_config.NumberColumn("Share (%)", format="%.2f"),
                },
                height=400, key="ov_city_table",
            )
