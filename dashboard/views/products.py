"""Products - catalogue performance, profitability and the discount trade-off.

Organised around the three questions a catalogue owner actually asks:
what sells, what earns, and what the discounting costs.
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
from ..config import DEFAULT_TOP_N, PALETTE
from ..metrics import build_metric_bundle, share_pct
from ..utils import (
    Filters,
    fmt_int,
    fmt_pct,
    fmt_pkr_compact,
    fmt_ratio,
    safe_div,
)


def render(filters: Filters) -> None:
    products = queries.product_performance(filters)
    if products.empty:
        st.warning("No products match the current filters.")
        return

    kpi = queries.kpi_metrics(filters)
    m = build_metric_bundle(kpi) if kpi else {}

    total_revenue = products["realised_revenue"].sum()
    total_profit = products["realised_profit"].sum()

    section("Catalogue in scope", "Adjusted to the current filters")
    kpi_grid(
        [
            Kpi("Products in scope", fmt_int(len(products)),
                "Matched by the current filters", PALETTE["neutral"]),
            Kpi("Realised revenue", fmt_pkr_compact(total_revenue),
                "Completed orders only", PALETTE["revenue"]),
            Kpi("Realised profit", fmt_pkr_compact(total_profit),
                f"Margin {fmt_pct(share_pct(total_profit, total_revenue))}", PALETTE["profit"]),
            Kpi("Units sold", fmt_int(products["units"].sum()),
                f"{fmt_ratio(safe_div(products['units'].sum(), m.get('total_orders')) or 0)} per order",
                PALETTE["neutral"]),
            Kpi("Average catalogue price",
                fmt_pkr_compact(products["catalogue_price"].mean()) if len(products) else "-",
                "List price, not the charged price", PALETTE["neutral"]),
        ]
    )

    callout(
        "<b>Two different prices.</b> <code>products.price</code> is the catalogue list "
        "price; <code>order_items.unit_price</code> is what the customer was actually "
        "charged. All revenue here uses the charged price.",
        tag="Definitions",
    )

    # ------------------------------------------------------------- leaders
    section("Product leaders",
            "Top performers under each measure - they are not the same products")
    top_n = st.slider("How many products to show", 5, 25, DEFAULT_TOP_N, step=5,
                      key="p_topn", label_visibility="visible")

    with panel(f"Top {top_n} by realised revenue", "The largest earners"):
        chart(charts.top_products(products, "realised_revenue", top=top_n), "p_rev")

    left, right = st.columns(2, gap="medium")
    with left:
        with panel(f"Top {top_n} by units sold", "The volume leaders"):
            chart(charts.top_products(products, "units", top=top_n, money=False), "p_units")
    with right:
        with panel(f"Top {top_n} by order frequency", "Products appearing in the most orders"):
            chart(charts.top_products(products, "order_count", top=top_n, money=False), "p_freq")

    # ------------------------------------------------------- profitability
    section("Profitability and category performance",
            "Revenue rank and margin rank are not the same ordering")
    category = queries.category_breakdown(filters)
    left, right = st.columns(2, gap="medium")
    with left:
        with panel("Revenue and profit by category", "Top 10 by realised revenue"):
            chart(charts.category_performance(category, top=10), "p_cat_chart")
    with right:
        with panel("Profit margin by category", "Against a 30% reference line"):
            chart(charts.margin_by_category(category), "p_margin")

    with panel("Category detail", "Sortable - click any column heading"):
        if not category.empty:
            cat_table = category.copy()
            cat_table["margin_pct"] = cat_table.apply(
                lambda r: share_pct(r["realised_profit"], r["realised_revenue"]), axis=1
            )
            data_table(
                cat_table[["category", "orders", "units", "realised_revenue",
                           "realised_profit", "margin_pct"]],
                {
                    "category": st.column_config.TextColumn("Category", width="medium"),
                    "orders": st.column_config.NumberColumn("Orders", format="%d"),
                    "units": st.column_config.NumberColumn("Units", format="%d"),
                    "realised_revenue": st.column_config.NumberColumn("Realised revenue (PKR)", format="%.0f"),
                    "realised_profit": st.column_config.NumberColumn("Realised profit (PKR)", format="%.0f"),
                    "margin_pct": st.column_config.NumberColumn("Margin (%)", format="%.2f"),
                },
                height=340, key="p_cat_table",
            )

    subcat = queries.subcategory_breakdown(filters)
    if not subcat.empty:
        with panel("Top subcategories by realised revenue", "Colour identifies the parent category"):
            chart(charts.subcategory_revenue(subcat, top=12), "p_subcat")

    # ------------------------------------------------------------- discount
    section("Product performance bands",
            "Completed orders only. Bands 0 / 1-5 / 6-10 / 11-15 / 16-20 / 21-25 / 26-30%")
    bands = queries.product_bands(filters)
    if bands.empty:
        st.info("No discounted lines in the selected scope.")
    else:
        left, right = st.columns(2, gap="medium")
        with left:
            with panel("Revenue per line and margin by band", "The margin cost of a discount"):
                chart(charts.product_bands(bands), "p_band")
        with right:
            with panel("Units per line by band", "The volume response to discounting"):
                chart(charts.units_per_line_by_band(bands), "p_band_units")

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
                height=320, key="p_band_table",
            )

        callout(
            "The <b>index</b> columns are each band's value divided by the no-discount "
            "band's value. An index of 1.00 means 'no different from not discounting'. "
            "This is a <b>description</b> of one synthetic dataset: product mix and "
            "basket size move at the same time as the discount, so no causal claim is "
            "made.",
            tag="Reading the index",
        )

    # ------------------------------------------------------ product table
    section("Product records",
            "Search by name, category, subcategory or brand. Click any column to sort.")

    search = st.text_input("Search products", placeholder="e.g. refrigerator, Grocery, Haier",
                           key="p_search")
    table = products.copy()
    table["margin_pct"] = table.apply(
        lambda r: share_pct(r["realised_profit"], r["realised_revenue"]), axis=1
    )
    if search.strip():
        needle = search.strip().lower()
        mask = (
            table["product_name"].str.lower().str.contains(needle, na=False)
            | table["category"].str.lower().str.contains(needle, na=False)
            | table["subcategory"].str.lower().str.contains(needle, na=False)
            | table["brand"].str.lower().str.contains(needle, na=False)
        )
        table = table[mask]
        st.caption(f"{len(table):,} of {len(products):,} products match '{search}'.")
        if table.empty:
            st.info("No products match that search. Try a shorter term.")
            return

    with panel(f"All {len(table):,} matching products", "Searchable and sortable"):
        data_table(
            table[["product_id", "product_name", "category", "subcategory", "brand",
                   "catalogue_price", "units", "order_count", "avg_discount_pct",
                   "total_cost", "realised_revenue", "realised_profit", "margin_pct"]],
            {
                "product_id": st.column_config.TextColumn("ID", width="small"),
                "product_name": st.column_config.TextColumn("Product", width="large"),
                "category": st.column_config.TextColumn("Category", width="small"),
                "subcategory": st.column_config.TextColumn("Subcategory", width="small"),
                "brand": st.column_config.TextColumn("Brand", width="small"),
                "catalogue_price": st.column_config.NumberColumn("Catalogue price (PKR)", format="%.0f"),
                "units": st.column_config.NumberColumn("Units", format="%d"),
                "order_count": st.column_config.NumberColumn("Orders", format="%d"),
                "avg_discount_pct": st.column_config.NumberColumn("Avg discount (%)", format="%.2f"),
                "total_cost": st.column_config.NumberColumn("Cost (PKR)", format="%.0f"),
                "realised_revenue": st.column_config.NumberColumn("Revenue (PKR)", format="%.0f"),
                "realised_profit": st.column_config.NumberColumn("Profit (PKR)", format="%.0f"),
                "margin_pct": st.column_config.NumberColumn("Margin (%)", format="%.2f"),
            },
            height=520, key="p_detail_table",
        )
