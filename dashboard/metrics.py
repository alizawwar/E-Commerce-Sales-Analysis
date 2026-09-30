"""Turning raw database output into the numbers the UI shows.

Kept separate from the queries and free of any Streamlit import so the metric
definitions can be unit-tested and re-checked against Phase 3 without starting
the app.

Every function is pure: raw dict/rows in, formatted values out.
"""

from __future__ import annotations

from typing import Any

from .utils import safe_div

# ---------------------------------------------------------------------------
# Rates and derived figures
# ---------------------------------------------------------------------------


def order_rates(kpi: dict[str, Any]) -> dict[str, float | None]:
    """Order-status rates as percentages of total orders.

    Return rate and cancellation rate are computed exactly as in Phase 3:
    the relevant status divided by *all* orders in scope.
    """
    total = kpi.get("total_orders") or 0
    return {
        "completion_rate": safe_div(100 * (kpi.get("completed_orders") or 0), total),
        "cancellation_rate": safe_div(100 * (kpi.get("cancelled_orders") or 0), total),
        "return_rate": safe_div(100 * (kpi.get("returned_orders") or 0), total),
        "pending_rate": safe_div(100 * (kpi.get("pending_orders") or 0), total),
    }


def financial_metrics(kpi: dict[str, Any]) -> dict[str, Any]:
    """Realised revenue, profit, margin, AOV and the loss rate.

    ``realised_*`` come from the query, which already restricts them to
    Completed orders. ``gross_order_value`` covers every selected status and is
    deliberately kept separate - the UI labels it as potential value.
    """
    revenue = kpi.get("realised_revenue") or 0.0
    profit = kpi.get("realised_profit") or 0.0
    completed = kpi.get("completed_orders") or 0
    gross = kpi.get("gross_order_value") or 0.0

    # "Did not complete" is Cancelled + Returned, matching Phase 3. It is NOT
    # gross - realised: that would also sweep in Pending orders, which have not
    # failed, they are still in flight. Mixing those two is exactly the mistake
    # this project is supposed to avoid.
    lost = kpi.get("value_not_completed")
    if lost is None:
        pending = kpi.get("value_pending") or 0.0
        lost = max(gross - revenue - pending, 0.0)
    pending_value = kpi.get("value_pending") or 0.0

    return {
        "realised_revenue": revenue,
        "realised_profit": profit,
        "gross_profit": profit,
        "margin_pct": safe_div(100 * profit, revenue),
        "average_order_value": safe_div(revenue, completed),
        "profit_per_order": safe_div(profit, completed),
        "gross_order_value": gross,
        "value_not_completed": lost,
        "value_pending": pending_value,
        "loss_rate_pct": safe_div(100 * lost, lost + revenue) if (lost + revenue) else None,
        "realised_share_pct": safe_div(100 * revenue, gross),
        "not_completed_pct": safe_div(100 * lost, gross),
        "pending_pct": safe_div(100 * pending_value, gross),
    }


def basket_metrics(kpi: dict[str, Any]) -> dict[str, Any]:
    """Basket-size style figures derived from the same single row of data."""
    total = kpi.get("total_orders") or 0
    units = kpi.get("units_total") or 0
    lines = kpi.get("line_count") or 0
    discounted = kpi.get("discounted_lines") or 0
    return {
        "units_total": units,
        "units_completed": kpi.get("units_completed") or 0,
        "lines_per_order": safe_div(lines, total),
        "units_per_order": safe_div(units, total),
        "discounted_line_share_pct": safe_div(100 * discounted, lines),
        "discount_value_realised": kpi.get("discount_value_realised") or 0.0,
    }


def margin_pct(revenue: Any, profit: Any) -> float | None:
    """Margin percentage for a table row, tolerant of zero revenue."""
    return safe_div(100 * (profit or 0), revenue or 0)


def aov_pct(revenue: Any, orders: Any) -> float | None:
    """Average order value for a table row."""
    return safe_div(revenue or 0, orders or 0)


def share_pct(value: Any, total: Any) -> float | None:
    """Share of a total as a percentage."""
    return safe_div(100 * (value or 0), total or 0)


def customer_segment(orders: int) -> str:
    """The deliberately simple, transparent segmentation rule.

    1 order  -> "One-time"
    2+ orders -> "Repeat"

    This is a rule, not a model. It is stated plainly in the UI so nobody
    mistakes it for something more sophisticated than it is.
    """
    return "Repeat" if orders and orders > 1 else "One-time"


def growth_change(first: Any, last: Any) -> float | None:
    """Percentage change between two comparable averages."""
    return safe_div(100 * ((last or 0) - (first or 0)), first or 0)


def build_metric_bundle(kpi: dict[str, Any]) -> dict[str, Any]:
    """One call that produces every derived figure the Overview page needs."""
    financial = financial_metrics(kpi)
    basket = basket_metrics(kpi)
    return {
        **kpi,
        **financial,
        **basket,
        **order_rates(kpi),
    }
