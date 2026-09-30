"""Phase 3 reference values - TEST FIXTURES ONLY.

These numbers are the headline results recorded in ``sql/sql_results_summary.md``
and produced by ``sql/14_headline_metrics.sql`` and
``sql/13_phase2_reconciliation.sql``.

They exist for exactly one purpose: letting
``scripts/verify_dashboard_metrics.py`` prove that the dashboard's own queries
reproduce the Phase 3 results. **No dashboard page imports this module, and no
KPI is ever rendered from it.** If a figure in the UI is wrong, the fix is the
query, not this file.

Each entry carries the tolerance Phase 3 itself used (0.01 for money and
percentages, exact for row counts).
"""

from __future__ import annotations

# metric -> (phase3_value, absolute_tolerance, description)
PHASE3_HEADLINE: dict[str, tuple[float, float, str]] = {
    "total_orders":            (12000, 0, "exact row count"),
    "completed_orders":        (9076, 0, "exact row count"),
    "pending_orders":          (1220, 0, "exact row count"),
    "cancelled_orders":        (774, 0, "exact row count"),
    "returned_orders":         (930, 0, "exact row count"),
    "registered_customers":    (1500, 0, "exact row count"),
    "active_customers":        (1440, 0, "distinct customers with any order"),
    "inactive_customers":      (60, 0, "registered minus active"),
    "products":                (300, 0, "catalogue size"),
    "line_count":              (30006, 0, "order line count"),
    "units_total":             (50694, 0, "all orders"),
    "units_completed":         (38406, 0, "completed orders only"),
    "completion_rate":         (75.63, 0.01, "completed / total"),
    "cancellation_rate":       (6.45, 0.01, "cancelled / total"),
    "return_rate":             (7.75, 0.01, "returned / total"),
    "pending_rate":            (10.17, 0.01, "pending / total"),
    "repeat_customer_rate":    (90.83, 0.01, "customers with >1 order / active"),
    "gross_order_value":       (845400583.33, 0.01, "every status - potential value"),
    "realised_revenue":        (632578305.60, 0.01, "Completed orders only"),
    "realised_profit":         (196295405.60, 0.01, "revenue - cost, Completed only"),
    "margin_pct":              (31.03, 0.01, "profit / revenue"),
    "average_order_value":     (69697.92, 0.01, "revenue / completed orders"),
    "profit_per_order":        (21627.96, 0.01, "profit / completed orders"),
    "lines_per_order":         (2.50, 0.01, "lines / orders"),
    "units_per_order":         (4.22, 0.01, "units / orders"),
    "discounted_line_share_pct": (51.46, 0.01, "lines with a discount / all lines"),
    "discount_value_realised": (44306902.65, 0.01, "discount given on completed orders"),
    "top_10_share_pct":        (3.60, 0.01, "top 10 customers / realised revenue"),
    "value_not_completed_pct": (15.15, 0.01, "cancelled+returned value / gross value"),
}

# Category realised revenue, used by the Products and Overview pages.
PHASE3_CATEGORY_REVENUE: dict[str, float] = {
    "Electronics": 177321318.73,
    "Home Appliances": 158512077.59,
    "Computers": 153812523.67,
    "Home & Kitchen": 42028660.26,
    "Fashion": 26808739.67,
    "Mobile Accessories": 21893346.44,
    "Sports": 18580377.78,
    "Beauty": 18449332.13,
    "Books": 7878236.58,
    "Grocery": 7293692.73,
}
