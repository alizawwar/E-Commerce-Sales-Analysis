"""Sales Analysis - the page that answers "how are sales performing?".

Organised as five questions rather than as a column of charts:

    1. Sales performance   trend, volume and the three money definitions
    2. Growth              complete-month comparison, and average order value
    3. Contribution        which categories, subcategories and cities carry it
    4. Basket              how large an order is, and what it is worth
    5. Discounts           the margin cost of a discount, band by band
"""

from __future__ import annotations

import streamlit as st

from .. import charts, queries
from ..components import (
    Kpi,
    callout,
    chart,
    data_table,
    finding,
    kpi_grid,
    panel,
    section,
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
    safe_div,
)


def render(filters: Filters) -> None:
    kpi = queries.kpi_metrics(filters)
    if not kpi:
        st.warning("No orders match the current filters.")
        return
    m = build_metric_bundle(kpi)

    # ------------------------------------------------------- 1. performance
    section("Sales performance", "Realised figures are Completed orders only")
    kpi_grid(
        [
            Kpi("Realised revenue", fmt_pkr_compact(m["realised_revenue"]),
                "Completed orders only", PALETTE["revenue"]),
            Kpi("Realised profit", fmt_pkr_compact(m["realised_profit"]),
                f"Margin {fmt_pct(m['margin_pct'])}", PALETTE["profit"]),
            Kpi("Gross / potential value", fmt_pkr_compact(m["gross_order_value"]),
                "Every selected status", PALETTE["neutral"]),
            Kpi("Average order value", fmt_pkr(m["average_order_value"], 0),
                "Realised / completed order", PALETTE["revenue"]),
            Kpi("Value not completed", fmt_pkr_compact(m["value_not_completed"]),
                f"{fmt_pct(m['not_completed_pct'])} of gross", PALETTE["danger"]),
        ]
    )
    kpi_grid(
        [
            Kpi("Profit per order", fmt_pkr(m["profit_per_order"], 0),
                "Realised profit / completed order", PALETTE["profit"]),
            Kpi("Value still pending", fmt_pkr_compact(m["value_pending"]),
                f"{fmt_pct(m['pending_pct'])} of gross", PALETTE["warning"]),
            Kpi("Completed orders", fmt_int(m["completed_orders"]),
                f"{fmt_pct(m['completion_rate'])} completion rate", PALETTE["success"]),
            Kpi("Units sold", fmt_int(m["units_total"]),
                f"{fmt_ratio(m['units_per_order'])} per order", PALETTE["neutral"]),
            Kpi("Discount given away", fmt_pkr_compact(m["discount_value_realised"]),
                f"{fmt_pct(m['discounted_line_share_pct'])} of lines", PALETTE["warning"]),
        ]
    )

    callout(
        "<b>Three different quantities, kept apart.</b> Realised revenue counts "
        "Completed orders. Gross / potential value counts every selected status. "
        "Value that did not complete counts only <b>Cancelled + Returned</b> - "
        "Pending orders are excluded from it, because a pending order has not "
        "failed, it is still in flight.",
        tag="Definitions",
    )

    trend = queries.monthly_trend(filters)
    if trend.empty:
        st.info("No orders in the selected date range.")
        return

    with panel("Realised revenue and profit by month", "Completed orders only"):
        chart(charts.revenue_profit_trend(trend), "s_trend")

    left, right = st.columns(2, gap="medium")
    with left:
        with panel("Order volume by month", "All selected statuses, completed overlaid"):
            chart(charts.order_volume_trend(trend), "s_volume")
    with right:
        with panel("Profit margin by category", "Where the money is actually kept"):
            category = queries.category_breakdown(filters)
            chart(charts.margin_by_category(category), "s_margin")

    # ----------------------------------------------------------- 2. growth
    section("Growth analysis", "Complete months only - 2026-09 is partial and excluded")
    growth = queries.growth_summary(filters)
    left, right = st.columns([1, 1.5], gap="medium")
    with left:
        if growth and growth.get("change_pct") is not None:
            change = growth["change_pct"]
            finding(
                "First six vs most recent six complete months",
                f"{change:+.2f}%",
                f"Average of {fmt_int(round(growth['last_six_avg_orders']))} orders a month "
                f"in the most recent six complete months against "
                f"{fmt_int(round(growth['first_six_avg_orders']))} in the first six, "
                f"across {fmt_int(growth.get('complete_months', 0))} complete months. "
                "This compares order counts, not revenue, and excludes the partial month "
                "at either end.",
                PALETTE["success"] if change > 0 else PALETTE["danger"],
            )
        else:
            st.info("Not enough complete months in the selected range to compare periods.")
    with right:
        with panel("Average order value by month", "Realised revenue / completed orders"):
            chart(charts.aov_trend(trend), "s_aov")

    # -------------------------------------------------- 3. contribution
    section("Revenue contribution", "Which categories, subcategories and cities carry it")
    with panel("Revenue and profit by category", "Top 10 by realised revenue"):
        chart(charts.category_performance(category, top=10), "s_cat")

    left, right = st.columns(2, gap="medium")
    with left:
        subcat = queries.subcategory_breakdown(filters)
        with panel("Top subcategories by realised revenue", "Colour identifies the parent category"):
            chart(charts.subcategory_revenue(subcat, top=12), "s_subcat")
    with right:
        city = queries.city_breakdown(filters)
        with panel("Revenue by shipping city", "Top 12 cities, leader highlighted"):
            chart(charts.city_revenue(city, top=12), "s_city")

    if not category.empty:
        with panel("Category detail", "Sortable - click any column heading"):
            table = category.copy()
            total = table["realised_revenue"].sum() or 1
            table["share_pct"] = table.apply(
                lambda r: share_pct(r["realised_revenue"], total), axis=1
            )
            table["margin_pct"] = table.apply(
                lambda r: share_pct(r["realised_profit"], r["realised_revenue"]), axis=1
            )
            data_table(
                table[["category", "orders", "units", "gross_order_value", "realised_revenue",
                       "realised_profit", "margin_pct", "share_pct"]],
                {
                    "category": st.column_config.TextColumn("Category", width="medium"),
                    "orders": st.column_config.NumberColumn("Orders", format="%d"),
                    "units": st.column_config.NumberColumn("Units", format="%d"),
                    "gross_order_value": st.column_config.NumberColumn("Gross value (PKR)", format="%.0f"),
                    "realised_revenue": st.column_config.NumberColumn("Realised revenue (PKR)", format="%.0f"),
                    "realised_profit": st.column_config.NumberColumn("Realised profit (PKR)", format="%.0f"),
                    "margin_pct": st.column_config.NumberColumn("Margin (%)", format="%.2f"),
                    "share_pct": st.column_config.NumberColumn("Share (%)", format="%.2f"),
                },
                height=380, key="s_cat_table",
            )

    # ------------------------------------------------------ 4. the basket
    section("Customer basket", "How large an order is, and what it is worth")
    size = queries.order_size_trend(filters)
    kpi_grid(
        [
            Kpi("Lines per order", fmt_ratio(m["lines_per_order"]),
                "Distinct products on an order", PALETTE["neutral"]),
            Kpi("Units per order", fmt_ratio(m["units_per_order"]),
                "Total quantity on an order", PALETTE["neutral"]),
            Kpi("Average order value", fmt_pkr(m["average_order_value"], 0),
                "Realised / completed order", PALETTE["revenue"]),
            Kpi("Revenue per line", fmt_pkr(safe_div(m["realised_revenue"], m["line_count"]) or 0, 0),
                "Realised revenue / order line", PALETTE["revenue"]),
            Kpi("Revenue per unit", fmt_pkr(safe_div(m["realised_revenue"], m["units_total"]) or 0, 0),
                "Realised revenue / unit sold", PALETTE["revenue"]),
        ]
    )
    if not size.empty:
        with panel("Average basket over time", "Units and lines per order, by month"):
            chart(charts.basket_size_trend(size), "s_basket")

    # ----------------------------------------------------- 5. discounting
    section("Discounts", "Completed orders only. Bands 0 / 1-5 / 6-10 / 11-15 / "
                         "16-20 / 21-25 / 26-30%")
    bands = queries.product_bands(filters)
    if bands.empty:
        st.info("No discounted lines in the selected scope.")
    else:
        left, right = st.columns(2, gap="medium")
        with left:
            with panel("Revenue per line and margin by discount band",
                       "Falling revenue per line as the discount deepens"):
                chart(charts.product_bands(bands), "s_band")
        with right:
            with panel("Units per line by discount band",
                       "The volume response to discounting"):
                chart(charts.units_per_line_by_band(bands), "s_band_units")

        base = bands.loc[bands["discount_band"] == "0%"]
        band_table = bands.copy()
        band_table["margin_pct"] = band_table.apply(
            lambda r: share_pct(r["realised_profit"], r["realised_revenue"]), axis=1
        )
        if not base.empty:
            base_rev = base["revenue_per_line"].iloc[0] or 1
            base_units = base["units_per_line"].iloc[0] or 1
            band_table["revenue_index"] = band_table["revenue_per_line"] / base_rev
            band_table["units_index"] = band_table["units_per_line"] / base_units
        with panel("Discount band detail", "Index columns compare each band with no discount"):
            data_table(
                band_table[["discount_band", "line_count", "units", "units_per_line",
                            "units_index", "revenue_per_line", "revenue_index",
                            "realised_revenue", "margin_pct"]],
                {
                    "discount_band": st.column_config.TextColumn("Discount", width="small"),
                    "line_count": st.column_config.NumberColumn("Lines", format="%d"),
                    "units": st.column_config.NumberColumn("Units", format="%d"),
                    "units_per_line": st.column_config.NumberColumn("Units/line", format="%.2f"),
                    "units_index": st.column_config.NumberColumn("Units index", format="%.2f"),
                    "revenue_per_line": st.column_config.NumberColumn("Revenue/line (PKR)", format="%.0f"),
                    "revenue_index": st.column_config.NumberColumn("Revenue index", format="%.2f"),
                    "realised_revenue": st.column_config.NumberColumn("Realised revenue (PKR)", format="%.0f"),
                    "margin_pct": st.column_config.NumberColumn("Margin (%)", format="%.2f"),
                },
                height=320, key="s_band_table",
            )

        callout(
            "The <b>index</b> columns are each band's value divided by the no-discount "
            "band's value. An index of 1.00 means 'no different from not discounting'. "
            "This is a <b>description</b> of one synthetic dataset: which products were "
            "discounted, their cost structure and their basket size all move together, "
            "so no causal claim is made.",
            tag="Reading the index",
        )

    # ------------------------------------------------ what did not work
    section("Value that did not work out",
            "Two different populations, deliberately not combined")
    failure = queries.payment_failure_detail(filters)
    if failure.empty:
        st.info("No data for the selected filters.")
        return

    left, right = st.columns(2, gap="medium")
    for col, (_, row) in zip((left, right), failure.iterrows()):
        is_payment = "Payment failed" in row["definition"]
        with col:
            finding(
                "Payment failure" if is_payment else "Orders that did not complete",
                fmt_pkr_compact(row["gross_order_value"]),
                f"{fmt_int(row['orders'])} orders, {fmt_pct(row['pct_of_gross'])} of "
                f"gross order value in the current scope.",
                PALETTE["danger"] if is_payment else PALETTE["warning"],
            )

    callout(
        "<b>Do not add these two numbers together.</b> <code>payment_status = "
        "'Failed'</code> is a <i>payment</i> outcome - the gateway or channel did not "
        "go through. <b>Cancelled / Returned</b> is an <i>order</i> outcome - the "
        "customer or the business changed their mind after payment. They overlap only "
        "partially, and in this dataset every failed payment sits on a Cancelled order.",
        tag="Do not add",
    )
    with panel("Value that did not complete, and payment failures", "As reported by the database"):
        data_table(
            failure,
            {
                "definition": st.column_config.TextColumn("Definition", width="large"),
                "orders": st.column_config.NumberColumn("Orders", format="%d"),
                "gross_order_value": st.column_config.NumberColumn("Value (PKR)", format="%.0f"),
                "pct_of_gross": st.column_config.NumberColumn("% of gross value", format="%.2f"),
            },
            height=180, key="s_failure_table",
        )
