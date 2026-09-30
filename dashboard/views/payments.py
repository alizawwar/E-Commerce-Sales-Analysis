"""Payments - method mix, outcome mix, failure behaviour and the heatmap.

Every query on this page follows the Phase 3 cardinality rule: ``order_items`` is
collapsed to one row per order *before* it is joined to ``payments``, so no
order's value can ever be counted twice. The rule is restated in the UI because
it is the single easiest mistake to make in this schema.

The page also never merges the two status columns. ``orders.status`` says
whether the order completed; ``payments.payment_status`` says whether the money
moved. Those are different populations, and in this dataset they disagree.
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
    finding,
    kpi_grid,
    panel,
    section,
)
from ..config import PALETTE, PAYMENT_STATUS_COLORS
from ..metrics import build_metric_bundle, share_pct
from ..utils import Filters, fmt_int, fmt_pct, fmt_pkr, fmt_pkr_compact


def render(filters: Filters) -> None:
    kpi = queries.kpi_metrics(filters)
    methods = queries.payment_method_summary(filters)
    if methods.empty:
        st.warning("No payments match the current filters.")
        return

    m = build_metric_bundle(kpi) if kpi else {}
    total_payments = int(methods["payments"].sum())
    total_failed = int(methods["failed"].sum())
    total_paid = int(methods["paid"].sum())
    total_refunded = int(methods["refunded"].sum())
    total_pending = int(methods["pending"].sum())
    overall_failure = share_pct(total_failed, total_payments)
    top_method = methods.iloc[0]

    # --------------------------------------------------- 1. method share
    section("Method mix", "One payment row per order - the payments table is 1-to-1 with orders")
    kpi_grid(
        [
            Kpi("Payments", fmt_int(total_payments),
                "One per order in scope", PALETTE["neutral"]),
            Kpi("Most used method", str(top_method["payment_method"]),
                f"{fmt_int(top_method['payments'])} payments, "
                f"{fmt_pct(share_pct(top_method['payments'], total_payments))}",
                PALETTE["revenue"], small_value=True),
            Kpi("Distinct methods", fmt_int(len(methods)),
                "Present in the current scope", PALETTE["neutral"]),
            Kpi("Realised revenue collected",
                fmt_pkr_compact(methods["realised_revenue"].sum()),
                "On Completed orders only", PALETTE["success"]),
            Kpi("Order value covered", fmt_pkr_compact(methods["gross_order_value"].sum()),
                "Every selected status", PALETTE["neutral"]),
        ]
    )

    # ------------------------------------------------------- 2. outcomes
    section("Payment outcomes", "The outcome of the payment, which is not the status of the order")
    kpi_grid(
        [
            Kpi("Paid", fmt_int(total_paid),
                f"{fmt_pct(share_pct(total_paid, total_payments))} of payments",
                PAYMENT_STATUS_COLORS["Paid"]),
            Kpi("Failed", fmt_int(total_failed),
                f"{fmt_pct(overall_failure)} failure rate",
                PAYMENT_STATUS_COLORS["Failed"]),
            Kpi("Pending", fmt_int(total_pending),
                f"{fmt_pct(share_pct(total_pending, total_payments))} not settled",
                PAYMENT_STATUS_COLORS["Pending"]),
            Kpi("Refunded", fmt_int(total_refunded),
                f"{fmt_pct(share_pct(total_refunded, total_payments))} of payments",
                PAYMENT_STATUS_COLORS["Refunded"]),
        ]
    )

    by_status = queries.payment_status_summary(filters)
    order_status = queries.order_status_breakdown(filters)
    payment_mix = (
        by_status.groupby("payment_status", as_index=False)["payments"].sum()
        if not by_status.empty else by_status
    )
    order_mix = (
        order_status.groupby("status", as_index=False)["orders"].sum()
        if not order_status.empty else order_status
    )

    left, right = st.columns(2, gap="medium")
    with left:
        with panel("Payment status mix",
                   "What happened to the payment - Paid, Failed, Pending, Refunded"):
            chart(charts.payment_status_distribution(payment_mix), "pm_status")
    with right:
        with panel("Order status mix",
                   "What happened to the order - a different population"):
            chart(charts.status_distribution(order_mix), "pm_order_status")

    callout(
        "<b>These two donuts answer different questions and must not be combined.</b> "
        "<code>orders.status</code> describes the order lifecycle; "
        "<code>payments.payment_status</code> describes the single payment attempt "
        "attached to that order. In this dataset every <b>Refunded</b> payment sits on "
        "a <b>Completed</b> order, so a refund reduces neither revenue nor the "
        "completion rate - it is a separate fact about the money, not the order.",
        tag="Order status vs payment status",
    )

    with panel("Payment outcome detail", "Sortable - click any column heading"):
        if not payment_mix.empty:
            table = payment_mix.copy()
            table["share_pct"] = table.apply(
                lambda r: share_pct(r["payments"], table["payments"].sum()), axis=1
            )
            value_by_status = (
                by_status.groupby("payment_status", as_index=False)["gross_order_value"].sum()
            )
            table = table.merge(value_by_status, on="payment_status", how="left")
            table["value_share_pct"] = table.apply(
                lambda r: share_pct(r["gross_order_value"],
                                    table["gross_order_value"].sum()), axis=1
            )
            data_table(
                table[["payment_status", "payments", "share_pct",
                       "gross_order_value", "value_share_pct"]],
                {
                    "payment_status": st.column_config.TextColumn("Payment status", width="small"),
                    "payments": st.column_config.NumberColumn("Payments", format="%d"),
                    "share_pct": st.column_config.NumberColumn("Share of payments (%)", format="%.2f"),
                    "gross_order_value": st.column_config.NumberColumn("Order value (PKR)", format="%.0f"),
                    "value_share_pct": st.column_config.NumberColumn("Share of value (%)", format="%.2f"),
                },
                height=200, key="pm_status_table",
            )

    # ------------------------------------------------------ 3. by method
    section("Method performance",
            "Volume, realised revenue and how often each method fails")
    left, right = st.columns([1, 1.25], gap="medium")
    with left:
        with panel("Payments by method", "The largest channels first"):
            chart(charts.payment_method_usage(methods), "pm_usage")
    with right:
        with panel("Failure rate by method",
                   "The dashed line is the portfolio average"):
            chart(charts.payment_failure_rate(methods), "pm_failure")

    method_table = methods.copy()
    method_table["payment_share_pct"] = method_table.apply(
        lambda r: share_pct(r["payments"], total_payments), axis=1
    )
    method_table["realised_share_pct"] = method_table.apply(
        lambda r: share_pct(r["realised_revenue"], methods["realised_revenue"].sum()), axis=1
    )
    method_table["realised_per_payment"] = method_table.apply(
        lambda r: (r["realised_revenue"] / r["payments"]) if r["payments"] else 0, axis=1
    )
    with panel("Method detail", "Volume, realised revenue and failure rate per method"):
        data_table(
            method_table[["payment_method", "payments", "orders", "paid", "failed",
                          "pending", "refunded", "failure_rate_pct",
                          "payment_share_pct", "realised_revenue",
                          "realised_per_payment"]],
            {
                "payment_method": st.column_config.TextColumn("Method", width="medium"),
                "payments": st.column_config.NumberColumn("Payments", format="%d"),
                "orders": st.column_config.NumberColumn("Orders", format="%d"),
                "paid": st.column_config.NumberColumn("Paid", format="%d"),
                "failed": st.column_config.NumberColumn("Failed", format="%d"),
                "pending": st.column_config.NumberColumn("Pending", format="%d"),
                "refunded": st.column_config.NumberColumn("Refunded", format="%d"),
                "failure_rate_pct": st.column_config.NumberColumn("Failure rate (%)", format="%.2f"),
                "payment_share_pct": st.column_config.NumberColumn("Share of payments (%)", format="%.2f"),
                "realised_revenue": st.column_config.NumberColumn("Realised revenue (PKR)", format="%.0f"),
                "realised_per_payment": st.column_config.NumberColumn("Realised per payment (PKR)", format="%.0f"),
            },
            height=320, key="pm_method_table",
        )

    # ------------------------------------------------------- 4. the grid
    section("Method by outcome", "Where every payment in scope sits")
    if by_status.empty:
        st.info("No payment detail for the selected filters.")
    else:
        with panel("Payment counts by method and status",
                   "Each cell is a count; the shading follows the same scale"):
            chart(charts.payment_status_heatmap(by_status), "pm_heat")

        with panel("Method and status detail", "Every cell of the grid above"):
            table = by_status.copy()
            table["share_of_method_pct"] = table.apply(
                lambda r: share_pct(r["payments"],
                                    int(methods.loc[methods["payment_method"] == r["payment_method"],
                                                    "payments"].sum()) or 1),
                axis=1,
            )
            table["avg_order_value"] = table.apply(
                lambda r: (r["gross_order_value"] / r["payments"]) if r["payments"] else 0, axis=1
            )
            data_table(
                table[["payment_method", "payment_status", "payments",
                       "share_of_method_pct", "gross_order_value", "avg_order_value"]],
                {
                    "payment_method": st.column_config.TextColumn("Method", width="medium"),
                    "payment_status": st.column_config.TextColumn("Status", width="small"),
                    "payments": st.column_config.NumberColumn("Payments", format="%d"),
                    "share_of_method_pct": st.column_config.NumberColumn("% of method", format="%.2f"),
                    "gross_order_value": st.column_config.NumberColumn("Order value (PKR)", format="%.0f"),
                    "avg_order_value": st.column_config.NumberColumn("Avg value per payment (PKR)", format="%.0f"),
                },
                height=420, key="pm_heat_table",
            )

    # ------------------------------------------------------ 5. the caveats
    section("What the payment data does not say",
            "Stated here rather than left for the reader to infer")
    left, right = st.columns(2, gap="medium")
    with left:
        finding(
            "Failure rate",
            fmt_pct(overall_failure),
            f"{fmt_int(total_failed)} of {fmt_int(total_payments)} payments in the "
            "current scope failed. A failure is a payment outcome; the order attached "
            "to it has its own separate status.",
            PALETTE["danger"],
        )
    with right:
        finding(
            "Refunded payments",
            fmt_int(total_refunded),
            "Refunded payments sit on Completed orders in this dataset, so refunds do "
            "not reduce realised revenue as reported here. Refunds were not netted "
            "against revenue anywhere in Phase 3.",
            PALETTE["returned"],
        )

    bullets(
        [
            "<b>One payment per order.</b> The <code>payments</code> table carries a "
            "UNIQUE constraint on <code>order_id</code>, so payment counts and order "
            "counts match on the same scope. A payment method mix cannot double-count.",
            "<b>Order value is collapsed before the join.</b> Each order's value is "
            "aggregated to a single row first, then joined to its payment. Summing "
            "<code>gross_order_value</code> across methods therefore gives exactly the "
            "in-scope order value, not a multiple of it.",
            "<b>Failure rate is not comparable to the order cancellation rate.</b> A "
            "failed payment and a cancelled order describe different events and the two "
            "populations only partly overlap.",
            "<b>No timing analysis is shown.</b> <code>payment_date</code> exists but a "
            "settlement-lag report is out of scope for this dashboard, so nothing here "
            "should be read as a claim about how quickly money moves.",
        ]
    )
