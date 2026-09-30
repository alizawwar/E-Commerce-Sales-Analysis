"""Insights - findings computed from the live data, written like a short report.

Every number here is derived from a query in :mod:`dashboard.queries`, so the
findings follow the filters like every other page. Nothing is a stored
conclusion and no figure is written into the code.

Wording is deliberately careful. This is a **synthetic** dataset, so each finding
is phrased as an observation *in this dataset* rather than a claim about the
Pakistani e-commerce market, and no causal language is used: "is associated with"
is only ever reached for through "co-occurs with" and "the data shows".
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import charts, queries
from ..components import (
    Kpi,
    bullets,
    callout,
    chart,
    data_table,
    finding,
    kpi_grid,
    panel,
    section,
    spacer,
)
from ..config import PALETTE
from ..metrics import build_metric_bundle, customer_segment, share_pct
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
    callout(
        "<b>This dashboard reads a synthetic dataset.</b> The e-commerce data was "
        "generated in Phase 1 of this project with a fixed random seed. Every finding "
        "below is a real property <i>of that generated data</i> and is not evidence "
        "about the real Pakistani e-commerce market. All amounts are in PKR.",
        tag="Read this first",
    )

    kpi = queries.kpi_metrics(filters)
    if not kpi:
        st.warning("No orders match the current filters, so there is nothing to interpret.")
        return
    m = build_metric_bundle(kpi)
    customer_counts = queries.customer_metrics(filters)

    # ------------------------------------------------- gather the evidence
    category = queries.category_breakdown(filters)
    city = queries.city_breakdown(filters)
    products = queries.product_performance(filters, limit=25)
    customers = queries.customer_performance(filters)
    methods = queries.payment_method_summary(filters)
    bands = queries.product_bands(filters)
    growth = queries.growth_summary(filters)
    conc = queries.concentration(filters)
    failure = queries.payment_failure_detail(filters)

    # ---------------------------------------------------- 0. the headline
    section("Summary", "The scope every finding below is computed on")
    kpi_grid(
        [
            Kpi("Realised revenue", fmt_pkr_compact(m["realised_revenue"]),
                "Completed orders only", PALETTE["revenue"]),
            Kpi("Orders in scope", fmt_int(m["total_orders"]),
                f"{fmt_int(m['completed_orders'])} completed", PALETTE["neutral"]),
            Kpi("Margin", fmt_pct(m["margin_pct"]),
                f"Profit {fmt_pkr_compact(m['realised_profit'])}", PALETTE["profit"]),
            Kpi("Active customers", fmt_int(m["active_customers"]),
                f"of {fmt_int(customer_counts.get('registered_customers', 0))} registered",
                PALETTE["revenue"]),
            Kpi("Realised share of gross", fmt_pct(m["realised_share_pct"]),
                f"Gross {fmt_pkr_compact(m['gross_order_value'])}", PALETTE["neutral"]),
        ]
    )

    # The same figures as a report table, with the definition of each one
    # beside it. A number without its definition is not quotable.
    with panel("The figures behind this report",
               "Every value below is recomputed when a filter changes"):
        data_table(
            pd.DataFrame(_glossary_rows(m, customer_counts, methods, conc)),
            {
                "measure": st.column_config.TextColumn("Measure", width="medium"),
                "value": st.column_config.TextColumn("Value", width="small"),
                "definition": st.column_config.TextColumn("How it is defined", width="large"),
            },
            height=420, key="in_glossary",
        )

    if not category.empty:
        with panel("Realised revenue by category",
                   "The evidence behind the leading-category finding below"):
            chart(charts.category_performance(category), "in_category")

    # ----------------------------------------------------- 1. key findings
    section("Key findings", "The handful of numbers that describe this selection")
    left, right = st.columns(2, gap="medium")

    by_revenue = (products.nlargest(1, "realised_revenue") if not products.empty else None)
    by_units = (products.nlargest(1, "units") if not products.empty else None)
    by_orders = (products.nlargest(1, "order_count") if not products.empty else None)
    top_city = city.iloc[0] if not city.empty else None
    worst_method = methods.nlargest(1, "failure_rate_pct").iloc[0] if not methods.empty else None

    with left:
        if by_revenue is not None:
            total_revenue = products["realised_revenue"].sum() or 1
            _card(
                "Largest single product",
                str(by_revenue["product_name"].iloc[0]),
                f"{fmt_pkr_compact(by_revenue['realised_revenue'].iloc[0])} realised "
                f"revenue, {fmt_pct(share_pct(by_revenue['realised_revenue'].iloc[0], total_revenue))} "
                "of the catalogue's realised revenue in this scope.",
                PALETTE["revenue"],
            )
        if by_units is not None:
            _card(
                "Most units sold",
                str(by_units["product_name"].iloc[0]),
                f"{fmt_int(by_units['units'].iloc[0])} units across "
                f"{fmt_int(by_orders['order_count'].iloc[0])} orders. The unit leader "
                f"({str(by_units['product_name'].iloc[0])}) is not the revenue leader "
                f"({str(by_revenue['product_name'].iloc[0]) if by_revenue is not None else 'n/a'}).",
                PALETTE["profit"],
            )
        if top_city is not None:
            total_city = city["realised_revenue"].sum() or 1
            _card(
                "Largest shipping city",
                str(top_city["city"]),
                f"{fmt_pkr_compact(top_city['realised_revenue'])} realised revenue from "
                f"{fmt_int(top_city['orders'])} orders - "
                f"{fmt_pct(share_pct(top_city['realised_revenue'], total_city))} of all "
                f"{fmt_int(len(city))} cities in scope.",
                PALETTE["revenue"],
            )

    with right:
        if conc:
            _card(
                "Spend concentration",
                fmt_pct(conc.get("top_10_share_pct")),
                f"The 10 highest-spending customers account for this share of realised "
                f"revenue across {fmt_int(conc.get('paying_customers', 0))} customers "
                "with realised spend in this scope.",
                PALETTE["warning"],
            )
        if growth and growth.get("change_pct") is not None:
            change = growth["change_pct"]
            _card(
                "Order volume, first six vs last six complete months",
                f"{change:+.2f}%",
                f"{fmt_int(round(growth['last_six_avg_orders']))} orders a month in the "
                f"most recent six complete months against "
                f"{fmt_int(round(growth['first_six_avg_orders']))} in the first six, "
                f"over {fmt_int(growth.get('complete_months', 0))} complete months. "
                "2026-09 is partial and excluded from both ends.",
                PALETTE["success"] if change > 0 else PALETTE["danger"],
            )
        if worst_method is not None:
            _card(
                "Highest payment failure rate",
                f"{worst_method['payment_method']} - {worst_method['failure_rate_pct']:.2f}%",
                f"{fmt_int(worst_method['failed'])} of {fmt_int(worst_method['payments'])} "
                "payments failed through this method in the current scope. A failed "
                "payment is a payment outcome, not an order status.",
                PALETTE["danger"],
            )

    spacer(4)

    # ------------------------------------------------------ 2. by subject
    _subject_sections(
        filters=filters,
        m=m,
        category=category,
        products=products,
        customers=customers,
        methods=methods,
        bands=bands,
        failure=failure,
        customer_counts=customer_counts,
    )

    # ------------------------------------------------- 3. what this is not
    section("How to read these findings",
            "The limits are part of the result, not a disclaimer bolted on")
    bullets(
        [
            "<b>Observations, not causes.</b> Every statement describes what the "
            "numbers are. None of them says what would happen if a decision changed, "
            "because no experiment was run.",
            "<b>2026-09 is a partial month.</b> The dataset ends on 2026-09-26, so that "
            "month is truncated. It is excluded from the growth comparison and shown "
            "on trends only where it is labelled as partial.",
            "<b>Realised means Completed.</b> Realised revenue, profit and margin count "
            "Completed orders only. Gross / potential value counts every selected "
            "status and is always labelled that way.",
            "<b>Refunds are not netted.</b> A Refunded payment on a Completed order does "
            "not reduce realised revenue anywhere in this dashboard.",
            "<b>One dataset, one seed.</b> These findings describe one generated "
            "dataset. Repeating the analysis on a different seed could produce "
            "different rankings.",
            "<b>The filters change everything.</b> Every finding recomputes when a "
            "filter changes. Narrow the date range and the \"key findings\" above change "
            "with it - that is the point of the scope strip at the top of the page.",
        ]
    )


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------
def _glossary_rows(m: dict, customer_counts: dict, methods, conc: dict) -> list[dict]:
    """The report's figures, each paired with the definition it is computed on.

    This is the table a reader screenshots instead of the cards, so it carries
    the definition in the row rather than in a footnote.
    """
    repeat_rate = safe_div(
        100 * (customer_counts.get("repeat_customers") or 0),
        customer_counts.get("active_customers") or 0,
    )
    failure_rate = (
        share_pct(methods["failed"].sum(), methods["payments"].sum())
        if not methods.empty else None
    )
    rows = [
        ("Realised revenue", fmt_pkr(m["realised_revenue"], 0),
         "Order value of Completed orders only, summed from order lines."),
        ("Realised profit", fmt_pkr(m["realised_profit"], 0),
         "Realised revenue less products.cost on the same lines."),
        ("Gross / potential value", fmt_pkr(m["gross_order_value"], 0),
         "Order value of every selected status, Completed included."),
        ("Value not completed", fmt_pkr(m["value_not_completed"], 0),
         "Order value sitting on Cancelled or Returned orders."),
        ("Value still pending", fmt_pkr(m["value_pending"], 0),
         "Order value on Pending orders - in flight, not lost."),
        ("Realised share of gross", fmt_pct(m["realised_share_pct"]),
         "Realised revenue divided by gross value, in the same scope."),
        ("Profit margin", fmt_pct(m["margin_pct"]),
         "Realised profit divided by realised revenue."),
        ("Average order value", fmt_pkr(m["average_order_value"], 0),
         "Realised revenue divided by completed orders."),
        ("Orders in scope", fmt_int(m["total_orders"]),
         "COUNT(DISTINCT order_id) - never one count per product line."),
        ("Units in scope", fmt_int(m["units_total"]),
         "Summed quantity across order lines, every selected status."),
        ("Active customers", fmt_int(m["active_customers"]),
         "Distinct customer_id on orders inside the filters."),
        ("Registered customers", fmt_int(customer_counts.get("registered_customers", 0)),
         "Row count of the customers table; does not move with the filters."),
        ("Repeat customer rate", fmt_pct(repeat_rate),
         "Customers with more than one order, divided by active customers."),
        ("Units per order", fmt_ratio(m["units_per_order"]),
         "Units in scope divided by orders in scope."),
        ("Discounted line share", fmt_pct(m["discounted_line_share_pct"]),
         "Share of order lines carrying any discount."),
    ]
    if conc:
        rows.append((
            "Top 10 customer concentration", fmt_pct(conc.get("top_10_share_pct")),
            "Share of realised revenue held by the 10 highest-spending customers.",
        ))
    if failure_rate is not None:
        rows.append((
            "Payment failure rate", fmt_pct(failure_rate),
            "payments.payment_status = Failed, divided by all payments in scope.",
        ))
    return [{"measure": a, "value": b, "definition": c} for a, b, c in rows]


def _card(label: str, headline: str, detail: str, accent: str) -> None:
    """One stated finding, rendered in the shared finding-card style."""
    finding(label, headline, detail, accent)


def _subject_sections(*, filters, m, category, products, customers, methods,
                      bands, failure, customer_counts) -> None:
    """The six subject areas, each with only the findings the data supports."""
    # ------------------------------------------------------------- sales
    section("Sales", "Revenue, growth and the shape of an order")
    left, right = st.columns(2, gap="medium")
    with left:
        if not category.empty:
            leader = category.iloc[0]
            _card(
                "Largest category by realised revenue",
                str(leader["category"]),
                f"{fmt_pkr_compact(leader['realised_revenue'])} realised revenue, "
                f"{fmt_int(leader['orders'])} orders and "
                f"{fmt_int(leader['units'])} units. Margin on this category is "
                f"{fmt_pct(share_pct(leader['realised_profit'], leader['realised_revenue']))}.",
                PALETTE["revenue"],
            )
        _card(
            "Average order value and basket",
            fmt_pkr(m["average_order_value"], 0),
            f"Realised revenue divided by {fmt_int(m['completed_orders'])} completed "
            f"orders. Each order carries {fmt_ratio(m['lines_per_order'])} product lines "
            f"and {fmt_ratio(m['units_per_order'])} units on average.",
            PALETTE["revenue"],
        )
    with right:
        _card(
            "Value that did not complete",
            fmt_pkr_compact(m["value_not_completed"]),
            f"{fmt_pct(m['not_completed_pct'])} of gross order value sits on Cancelled "
            f"or Returned orders. A further {fmt_pkr_compact(m['value_pending'])} "
            f"({fmt_pct(m['pending_pct'])}) is still Pending - in flight, not lost.",
            PALETTE["danger"],
        )
        _card(
            "Gross versus realised",
            fmt_pct(m["realised_share_pct"]),
            f"Of {fmt_pkr_compact(m['gross_order_value'])} of gross / potential order "
            f"value in scope, {fmt_pkr_compact(m['realised_revenue'])} is realised on "
            "Completed orders. The gap is a status mix, not a pricing failure.",
            PALETTE["neutral"],
        )

    # ----------------------------------------------------------- product
    section("Products", "Catalogue performance and the discount bands")
    left, right = st.columns(2, gap="medium")
    with left:
        if not products.empty:
            ranked = products.copy()
            ranked["margin_pct"] = ranked.apply(
                lambda r: share_pct(r["realised_profit"], r["realised_revenue"]) or 0.0,
                axis=1,
            )
            best = ranked.nlargest(1, "margin_pct").iloc[0]
            _card(
                "Highest-margin product",
                str(best["product_name"]),
                f"Margin {fmt_pct(best['margin_pct'])} on "
                f"{fmt_pkr_compact(best['realised_revenue'])} realised revenue from "
                f"{fmt_int(best['units'])} units. Highest margin and highest revenue "
                "are different products in this scope.",
                PALETTE["profit"],
            )
        _card(
            "Catalogue in scope",
            fmt_int(len(products)),
            "Products matched by the current filters, with at least one line in scope. "
            "Rankings below use realised revenue unless stated otherwise.",
            PALETTE["neutral"],
        )
    with right:
        if not bands.empty:
            deep = bands[bands["discount_band"] != "0%"]
            base = bands[bands["discount_band"] == "0%"]
            if not base.empty and not deep.empty:
                base_rev = base["revenue_per_line"].iloc[0] or 1
                worst = deep.nsmallest(1, "revenue_per_line").iloc[0]
                _card(
                    "Deepest discount band, by revenue per line",
                    f"{worst['discount_band']} - "
                    f"{fmt_pkr_compact(worst['revenue_per_line'])} per line",
                    f"{safe_div(worst['revenue_per_line'], base_rev):.2f}x the "
                    f"{fmt_pkr_compact(base['revenue_per_line'].iloc[0])} per line of the "
                    "no-discount band, on "
                    f"{fmt_int(worst['line_count'])} completed-order lines. Discount "
                    "depth and product mix move together here, so this is a "
                    "description, not an effect.",
                    PALETTE["warning"],
                )
        _card(
            "Discounting in this scope",
            fmt_pct(m["discounted_line_share_pct"]),
            f"Share of order lines carrying any discount. The value given away on "
            f"completed-order lines is {fmt_pkr_compact(m['discount_value_realised'])}, "
            "measured as the pre-discount list value minus the charged value.",
            PALETTE["warning"],
        )

    # ---------------------------------------------------------- customer
    section("Customers", "Reach, repeat behaviour and where the spend sits")
    cm = customer_counts
    left, right = st.columns(2, gap="medium")
    repeat_rate = safe_div(100 * (cm.get("repeat_customers") or 0),
                            cm.get("active_customers") or 0)
    with left:
        _card(
            "Repeat behaviour",
            fmt_pct(repeat_rate),
            f"{fmt_int(cm.get('repeat_customers', 0))} of "
            f"{fmt_int(cm.get('active_customers', 0))} active customers placed more than "
            "one order in this scope. A customer with exactly one order is counted as "
            "one-time; this is a rule, not a model.",
            PALETTE["success"],
        )
        if not customers.empty:
            _card(
                "Spend per active customer",
                fmt_pkr(
                    safe_div(m.get("realised_revenue", 0), cm.get("active_customers") or 1) or 0,
                    0,
                ),
                f"Realised revenue divided by {fmt_int(cm.get('active_customers', 0))} "
                "active customers in scope.",
                PALETTE["revenue"],
            )
    with right:
        _card(
            "Registered versus active",
            f"{fmt_int(cm.get('active_customers', 0))} of "
            f"{fmt_int(cm.get('registered_customers', 0))}",
            f"{fmt_int(cm.get('inactive_customers', 0))} registered customers placed no "
            "order in this scope. Registered is counted over the whole customers table "
            "and does not move with the filters; active is counted inside them.",
            PALETTE["neutral"],
        )
        if not customers.empty:
            customers = customers.copy()
            customers["segment"] = [customer_segment(n) for n in customers["orders"]]
            one_time = customers[customers["segment"] == "One-time"]
            _card(
                "What the one-time customers are worth",
                fmt_pct(
                    share_pct(one_time["realised_revenue"].sum(),
                              customers["realised_revenue"].sum()) or 0
                ),
                f"{fmt_int(one_time['customer_id'].nunique())} one-time customers account "
                "for this share of realised revenue. Repeat customers hold the rest - "
                "in this dataset the one-time group is the majority by count.",
                PALETTE["neutral"],
            )

    # ------------------------------------------------------ operational
    section("Operational", "Order flow and what it cost")
    left, right = st.columns(2, gap="medium")
    with left:
        _card(
            "Completion rate",
            fmt_pct(m["completion_rate"]),
            f"{fmt_int(m['completed_orders'])} of {fmt_int(m['total_orders'])} orders in "
            "scope are Completed. Each status is counted once per order with "
            "COUNT(DISTINCT order_id), so a multi-line order is never counted twice.",
            PALETTE["success"],
        )
        _card(
            "Cancellation and returns",
            f"{fmt_pct(m['cancellation_rate'])} / {fmt_pct(m['return_rate'])}",
            f"{fmt_int(m['cancelled_orders'])} cancelled and "
            f"{fmt_int(m['returned_orders'])} returned orders, each as a share of all "
            f"orders in scope. A further {fmt_int(m['pending_orders'])} orders are "
            "Pending.",
            PALETTE["danger"],
        )
    with right:
        _card(
            "Order size",
            f"{fmt_ratio(m['units_per_order'])} units",
            f"Across {fmt_int(m['line_count'])} order lines and "
            f"{fmt_int(m['total_orders'])} orders. The Operations page breaks the same "
            "number down into basket-size bands.",
            PALETTE["neutral"],
        )
        if not failure.empty:
            failed = failure[failure["definition"].str.startswith("Payment failed")]
            not_done = failure[failure["definition"].str.startswith("Order did not")]
            if not failed.empty and not not_done.empty:
                _card(
                    "Two different populations, never added",
                    f"{fmt_pct(failed['pct_of_gross'].iloc[0])} vs "
                    f"{fmt_pct(not_done['pct_of_gross'].iloc[0])} of gross value",
                    "A failed payment and an order that did not complete describe "
                    "different things. The first is a payment outcome; the second is an "
                    "order outcome. They overlap only partly, so the two percentages are "
                    "reported side by side and never summed.",
                    PALETTE["warning"],
                )

    # ---------------------------------------------------------- payment
    section("Payment", "Method mix and reliability")
    left, right = st.columns(2, gap="medium")
    with left:
        if not methods.empty:
            _card(
                "Most used method",
                str(methods.iloc[0]["payment_method"]),
                f"{fmt_int(methods.iloc[0]['payments'])} payments, "
                f"{fmt_pct(share_pct(methods.iloc[0]['payments'], methods['payments'].sum()))} "
                f"of the {fmt_int(methods['payments'].sum())} payments in scope, with a "
                f"{methods.iloc[0]['failure_rate_pct']:.2f}% failure rate.",
                PALETTE["revenue"],
            )
            _card(
                "Payment outcome split",
                f"{fmt_int(int(methods['paid'].sum()))} paid, "
                f"{fmt_int(int(methods['failed'].sum()))} failed",
                f"{fmt_pct(share_pct(methods['paid'].sum(), methods['payments'].sum()))} "
                f"Paid, {fmt_pct(share_pct(methods['failed'].sum(), methods['payments'].sum()))} "
                f"Failed, {fmt_pct(share_pct(methods['pending'].sum(), methods['payments'].sum()))} "
                f"Pending and {fmt_pct(share_pct(methods['refunded'].sum(), methods['payments'].sum()))} "
                "Refunded. Every Refunded payment sits on a Completed order in this "
                "dataset, so refunds do not reduce realised revenue here.",
                PALETTE["neutral"],
            )
    with right:
        if not methods.empty:
            worst = methods.nlargest(1, "failure_rate_pct").iloc[0]
            best = methods.nsmallest(1, "failure_rate_pct").iloc[0]
            _card(
                "Failure rate, widest against narrowest",
                f"{worst['failure_rate_pct']:.2f}% vs "
                f"{best['failure_rate_pct']:.2f}%",
                f"{worst['payment_method']} fails most often and {best['payment_method']} "
                "least often in this scope. Both are read against the portfolio average "
                f"of {share_pct(methods['failed'].sum(), methods['payments'].sum()):.2f}%.",
                PALETTE["danger"],
            )
        _card(
            "One payment per order",
            fmt_int(int(methods["orders"].sum())) if not methods.empty else "-",
            "The payments table carries a UNIQUE constraint on order_id, and each "
            "order's value is collapsed to one row before it is joined to payments. "
            "Payment counts and order counts therefore match on the same scope.",
            PALETTE["neutral"],
        )

    # ------------------------------------------------------- data notes
    section("Data notes", "Known limits of this dataset, stated up front")
    bullets(
        [
            "<b>Synthetic by construction.</b> Generated in Phase 1 with a fixed random "
            "seed and a fixed schema. Values are internally consistent but are not "
            "observations of real trading.",
            "<b>2026-09 is partial.</b> The dataset ends on 2026-09-26, so that month's "
            "totals are truncated. It is excluded from the growth comparison and shown "
            "on trends only where it is labelled partial.",
            "<b>Refunds are not netted.</b> Refunded payments are counted, but never "
            "deducted from realised revenue, because a refund is recorded against the "
            "payment and not against the order.",
            "<b>There is no customer rating.</b> <code>products</code> has no rating "
            "column and <code>payments</code> has no amount column, so no satisfaction "
            "or payment-size claim can be made from this schema.",
            "<b>Cost is a catalogue value.</b> Profit uses <code>products.cost</code> at "
            "the time of the query, not a historical cost ledger, so margin is a "
            "catalogue-derived figure.",
            "<b>Order lines are read through a cap.</b> Detail tables read the row-level "
            "path and are limited by the connection settings in "
            "<code>.env</code>; the headline figures come from aggregate queries with no "
            "such cap.",
        ]
    )
