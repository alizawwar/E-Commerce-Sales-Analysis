"""Small shared helpers: formatting and the filter state object.

Keeping formatting in one place is what stops the dashboard from showing
``PKR 632578305.6`` on one card and ``PKR 632.6M`` on the next.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Sequence

import pandas as pd

from .config import ORDER_STATUSES

CURRENCY = "PKR"


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def fmt_pkr(value: Any, decimals: int = 0) -> str:
    """Format a money value in PKR with thousands separators.

    ``fmt_pkr(632578305.6)`` -> ``PKR 632,578,306``
    """
    if value is None or pd.isna(value):
        return "-"
    return f"{CURRENCY} {float(value):,.{decimals}f}"


def fmt_pkr_compact(value: Any) -> str:
    """Compact money for KPI cards: ``PKR 632.6M``.

    Falls back to plain formatting below one million so small numbers stay
    readable instead of turning into ``PKR 0.0K``.
    """
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000_000_000:
        return f"{sign}{CURRENCY} {value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"{sign}{CURRENCY} {value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{sign}{CURRENCY} {value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{sign}{CURRENCY} {value / 1_000:.1f}K"
    return f"{sign}{CURRENCY} {value:,.0f}"


def fmt_pkr_axis(value: Any) -> str:
    """Axis-label friendly money, e.g. ``600M`` (no currency symbol)."""
    if value is None or pd.isna(value):
        return ""
    value = float(value)
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.0f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:.0f}"


def fmt_int(value: Any) -> str:
    """Thousands-separated integer."""
    if value is None or pd.isna(value):
        return "-"
    return f"{int(round(float(value))):,}"


def fmt_pct(value: Any, decimals: int = 2) -> str:
    """Percentage from a 0-100 value. ``62.5`` -> ``62.50%``."""
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.{decimals}f}%"


def fmt_ratio(value: Any, decimals: int = 2) -> str:
    """Format a plain ratio, e.g. ``4.22``."""
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{decimals}f}"


def safe_div(numerator: Any, denominator: Any) -> float | None:
    """Divide, returning ``None`` instead of raising or producing inf.

    MySQL runs with ``ERROR_FOR_DIVISION_BY_ZERO`` enabled, and Python would
    happily emit ``inf`` for a 0/0 that slips through, so divisions are always
    routed through here.
    """
    if numerator is None or denominator is None:
        return None
    if pd.isna(numerator) or pd.isna(denominator):
        return None
    if float(denominator) == 0:
        return None
    return float(numerator) / float(denominator)


# ---------------------------------------------------------------------------
# Filter state
# ---------------------------------------------------------------------------
@dataclass
class Filters:
    """The global filter selection shared by every page.

    Semantics
    ---------
    * ``date_from`` / ``date_to``   -> ``orders.order_date``
    * ``cities``                    -> ``orders.shipping_city`` (where it ships)
    * ``statuses``                  -> ``orders.status``
    * ``payment_methods``           -> ``payments.payment_method``
    * ``categories`` / ``subcategories`` -> ``products.category`` /
      ``products.subcategory``, applied at **line level**.

    Line-level category filtering is deliberate: the revenue shown is the
    revenue of the selected product lines, not the whole value of every order
    that happened to contain one of them. Order counts are always
    ``COUNT(DISTINCT order_id)`` so a multi-line order is never counted twice.
    """

    date_from: date = date(2024, 10, 1)
    date_to: date = date(2026, 9, 26)
    cities: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    subcategories: list[str] = field(default_factory=list)
    # Default is *every* status, not just Completed. The status filter is a lens
    # on which orders to include; the word "realised" is applied separately and
    # always means Completed. Defaulting the filter to Completed would silently
    # change the denominator of every rate and would no longer reconcile with
    # the Phase 3 headline figures.
    statuses: list[str] = field(default_factory=lambda: list(ORDER_STATUSES))
    payment_methods: list[str] = field(default_factory=list)

    def normalised(self) -> "Filters":
        """Return a copy with an empty status selection replaced by all statuses.

        An empty ``statuses`` list is a degenerate state: it cannot be reached
        from the sidebar (the widget always yields at least one value) but it
        can be constructed in code, and leaving it as-is would make the SQL
        fragment ``1 = 1``, i.e. "every status", which silently contradicts the
        intent of "nothing selected". The UI reports the empty selection
        separately; the data layer refuses to guess.
        """
        if self.statuses:
            return self
        return replace(self, statuses=list(ORDER_STATUSES))

    @property
    def is_default(self) -> bool:
        """True when no filter is narrowing the dataset."""
        return (
            not self.cities
            and not self.categories
            and not self.subcategories
            and not self.payment_methods
            and sorted(self.statuses) == sorted(ORDER_STATUSES)
        )

    @property
    def active_count(self) -> int:
        """How many filters are currently narrowing the view."""
        return sum(
            [
                bool(self.cities),
                bool(self.categories),
                bool(self.subcategories),
                sorted(self.statuses) != sorted(ORDER_STATUSES),
                bool(self.payment_methods),
                self.date_from != date(2024, 10, 1) or self.date_to != date(2026, 9, 26),
            ]
        )

    def describe(self) -> list[str]:
        """Short human-readable chips describing the active filters."""
        chips: list[str] = []
        if self.cities:
            chips.append(f"City: {', '.join(self.cities)}")
        if self.categories:
            chips.append(f"Category: {', '.join(self.categories)}")
        if self.subcategories:
            chips.append(f"Subcategory: {', '.join(self.subcategories)}")
        if sorted(self.statuses) != sorted(ORDER_STATUSES):
            chips.append(f"Status: {', '.join(self.statuses) if self.statuses else 'none'}")
        if self.payment_methods:
            chips.append(f"Payment: {', '.join(self.payment_methods)}")
        return chips


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------
def empty_state(message: str, hint: str | None = None) -> None:
    """Render a consistent 'nothing to show' block. Imported lazily for tests."""
    import streamlit as st

    st.info(message)
    if hint:
        st.caption(hint)


def ordered_categories(frame: pd.DataFrame) -> list[str]:
    """Category order used consistently so colours stay stable between pages."""
    if frame.empty or "category" not in frame.columns:
        return []
    preferred = [
        "Electronics", "Home Appliances", "Computers", "Home & Kitchen", "Fashion",
        "Mobile Accessories", "Sports", "Beauty", "Books", "Grocery",
    ]
    present = set(frame["category"].dropna())
    ordered = [c for c in preferred if c in present]
    ordered += sorted(present - set(ordered))
    return ordered


def order_status_order(values: Sequence[str]) -> list[str]:
    """Business-meaningful status order: success, pending, cancelled, returned."""
    order = ["Completed", "Pending", "Cancelled", "Returned"]
    present = set(values)
    return [s for s in order if s in present] + sorted(present - set(order))
