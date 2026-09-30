"""Configuration for the E-Commerce Analytics Dashboard (Phase 4).

Everything that is environment specific lives here: database credentials, the
visual design system, and page metadata.

SECURITY
    Credentials are read from Streamlit's secret store when one is available -
    that is how a hosted deployment (Streamlit Community Cloud and friends)
    supplies them - and otherwise from environment variables, optionally seeded
    from a local ``.env`` file. No password is stored in this repository.
    ``.env`` and ``.streamlit/secrets.toml`` are both listed in ``.gitignore``.

    Secrets are consulted *first* so a hosted app is configured the way its
    platform expects. Locally there is no secret store, the lookup resolves to
    "absent", and the ``.env`` / environment path behaves exactly as before.

METRIC DEFINITIONS
    The definitions in ``METRIC_DEFINITIONS`` are the same ones used in Phase 3
    (see ``sql/README.md``). They are reproduced here so the UI, the docstrings
    and the SQL cannot drift apart silently:

        line revenue   = quantity * unit_price * (1 - discount_percent / 100)
        realised       = Completed orders only
        gross/potential= every selected order status
        profit         = revenue - quantity * products.cost
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"

# A local .env is a convenience for running on your own machine. It is never
# committed (see .gitignore). Values already present in the real environment
# win over it, and a hosted app has no .env at all - it uses st.secrets.
load_dotenv(PROJECT_ROOT / ".env")

# Sentinel distinguishing "secrets not looked up yet" from "there is no secret
# store", so the lookup happens once and its absence is remembered too.
_UNSET = object()
_SECRETS: Any = _UNSET


class ConfigError(RuntimeError):
    """Raised when the application is not configured correctly."""


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DatabaseConfig:
    """Connection settings for the MySQL analytics database."""

    host: str
    port: int
    name: str
    user: str
    password: str
    connect_timeout: int = 10
    charset: str = "utf8mb4"

    @property
    def label(self) -> str:
        """Human readable target, safe to show in the UI (contains no password)."""
        return f"{self.user}@{self.host}:{self.port}/{self.name}"


def _streamlit_secrets() -> Mapping[str, Any] | None:
    """Return Streamlit's secret store, or ``None`` when there isn't one.

    ``st.secrets`` *raises* rather than returning an empty mapping when no
    secrets file exists, which is the normal case for local development and for
    the offline test scripts. It is also only meaningful inside a Streamlit
    runtime, so the import is local and every failure mode collapses to
    ``None``.

    The result is cached because :func:`load_db_config` runs on every query and
    building the lookup each time would re-raise on every call. The cache is
    deliberately a single ``None``/mapping result rather than a per-key one, so
    a key that is absent from the store is re-checked against the environment
    instead of being remembered as missing.
    """
    global _SECRETS
    if _SECRETS is not _UNSET:
        return _SECRETS
    try:
        import streamlit as st  # local import: keeps this module importable
                                   # without Streamlit (e.g. the SQL scripts)
        _SECRETS = st.secrets
    except Exception:  # noqa: BLE001 - any failure means "no secret store"
        _SECRETS = None
    return _SECRETS


def _from_secrets(key: str) -> str | None:
    """Read one key from Streamlit's secret store, or ``None`` if not there."""
    secrets = _streamlit_secrets()
    if secrets is None:
        return None
    try:
        value = secrets[key]
    except Exception:  # noqa: BLE001 - missing key, or no secrets configured
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _env(key: str, default: str | None = None) -> str:
    """Resolve one setting, preferring Streamlit secrets over the environment.

    Order: ``st.secrets`` -> ``os.environ``. Both are the same five names, so a
    value set in either place is used without further configuration.
    """
    secret = _from_secrets(key)
    if secret is not None:
        return secret

    value = os.getenv(key, default)
    if value is None or not str(value).strip():
        raise ConfigError(
            f"Missing required database setting '{key}'. Set it as a Streamlit "
            "secret (Settings -> Secrets) when the app is hosted, or copy "
            ".env.example to .env and fill it in when running locally."
        )
    return str(value).strip()


def load_db_config() -> DatabaseConfig:
    """Build a :class:`DatabaseConfig` from the environment.

    Raises :class:`ConfigError` with an actionable message when something is
    missing, so the UI can explain what to do instead of crashing.
    """
    try:
        port = int(_env("DB_PORT", "3306"))
    except ValueError as exc:
        raise ConfigError("DB_PORT must be a whole number, for example 3306.") from exc

    return DatabaseConfig(
        host=_env("DB_HOST", "localhost"),
        port=port,
        name=_env("DB_NAME", "ecommerce_sales_analysis"),
        user=_env("DB_USER"),
        password=os.getenv("DB_PASSWORD", ""),
    )


# ---------------------------------------------------------------------------
# Metric definitions (single source of truth, mirrored from Phase 3)
# ---------------------------------------------------------------------------
METRIC_DEFINITIONS = {
    "realised_revenue": "quantity x unit_price x (1 - discount_percent/100), Completed orders only",
    "realised_profit": "realised revenue - quantity x products.cost, Completed orders only",
    "gross_order_value": "same revenue formula across every selected order status (value attempted)",
    "average_order_value": "realised revenue / completed orders",
    "active_customer": "a registered customer with at least one order",
    "repeat_customer": "an active customer with more than one order",
}

ORDER_STATUSES = ["Completed", "Pending", "Cancelled", "Returned"]

PAYMENT_STATUSES = ["Paid", "Pending", "Failed", "Refunded"]

# 2026-09 is incomplete (the dataset ends on 2026-09-26). Month-over-month
# comparisons exclude it, exactly as in sql/11_advanced_analysis.sql.
PARTIAL_MONTH = "2026-09"

# ---------------------------------------------------------------------------
# Design system
# ---------------------------------------------------------------------------
# A restrained dark business-intelligence palette, violet/indigo leaning. Colour
# carries meaning: violet = revenue, cyan = profit, emerald = success, amber =
# pending, rose = failure, pink = returns, muted violet-grey = neutral.
#
# Every hue is picked to hold its contrast against a near-black canvas, so a
# chart series never has to be brightened to stay readable, which is what would
# otherwise turn a dark theme into a neon one.
PALETTE = {
    "revenue": "#8B7CFF",
    # Two different "quiet" violets, because what "quiet" means depends on the
    # surface behind the mark. On a light card a de-emphasised bar is a *lighter*
    # tint of the accent and still recedes, so `revenue_soft` reads correctly as
    # accent-tinted text. On this near-black canvas the same tint is the
    # brightest thing in the frame, so every "highlight the leader, mute the
    # rest" chart had its hierarchy inverted - eleven loud bars and one quiet
    # one. `revenue_dim` is the dark-surface equivalent: dimmer than the accent
    # (luminance 0.047 against the accent's 0.271) but still clearly above the
    # card it sits on.
    "revenue_soft": "#C4BDFF",
    "revenue_dim": "#3A3180",
    "profit": "#22D3EE",
    "profit_soft": "#A5F3FC",
    "success": "#34D399",
    "warning": "#FBBF24",
    "danger": "#FB7185",
    "returned": "#F472B6",
    "neutral": "#8A85AD",
    "text": "#F4F2FF",
    "text_muted": "#8A85AD",
    "border": "#2A2650",
    "surface": "#15132B",
    "background": "#0B0A1A",
}

# ---------------------------------------------------------------------------
# Surface / type tokens
# ---------------------------------------------------------------------------
# Every visual value the UI uses lives here, so the whole application can be
# restyled from one dictionary instead of hunting hex codes through the CSS and
# the Plotly builders. ``components.inject_styles`` publishes these as CSS
# custom properties on ``:root`` and ``charts.BASE_LAYOUT`` reads the same keys,
# which is what keeps the HTML cards and the Plotly figures visually identical.
#
# Streamlit 1.64 resolves its own theme through generated emotion classes and
# exposes no theme CSS variables, so the appearance is pinned in
# ``.streamlit/config.toml`` and these tokens are the matching source of truth.
# The steps between canvas / card / card_alt / inset are deliberately small: on
# a dark canvas a large jump reads as a different application rather than as
# depth, while a small one reads as a surface.
SURFACE = {
    "canvas": "#0B0A1A",       # app background behind every card
    "sidebar": "#0E0C21",      # the sidebar is a shade off the canvas, not black
    "card": "#15132B",         # card / panel fill
    "card_alt": "#1C1938",     # subtle fill: chips, inactive rows
    "inset": "#221E45",        # table header, inline code, grouped backgrounds
    "border": "#2A2650",       # hairline card and table borders
    "border_soft": "#211E42",  # faint separators inside a card
    "grid": "#241F4A",         # chart gridlines
    "text": "#F4F2FF",         # headings, values
    "text_soft": "#B8B3D9",    # body copy
    "text_muted": "#8A85AD",   # labels, captions, axis ticks
    "accent": "#8B7CFF",       # primary brand accent
    "accent_2": "#5B4FD6",     # gradient partner for the brand mark
    "accent_soft": "#221E4A",  # primary tinted fill
    "shadow": "0 1px 2px rgba(0, 0, 0, 0.34), 0 1px 3px rgba(0, 0, 0, 0.26)",
    "shadow_lift": "0 6px 18px rgba(0, 0, 0, 0.48)",
}

# One spacing / radius scale, used by both the CSS and the layout helpers so
# card padding and gap stay in step. The radius is modest on purpose: a dark
# dashboard with large radii reads as consumer app chrome, not as a BI tool.
LAYOUT = {
    "radius": "10px",
    "radius_sm": "7px",
    "radius_pill": "999px",
    "gutter": "0.85rem",
    "page_max_width": "1680px",
    "sidebar_width": "272px",
}

# Font scale. Inter is not bundled, so the stack falls back to the system UI
# face; the dashboard must look right without a webfont request.
FONT_STACK = (
    '"Inter", "Segoe UI Variable Text", "Segoe UI", -apple-system, '
    'BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif'
)
FONT_MONO = '"JetBrains Mono", "Cascadia Mono", Consolas, "SF Mono", Menlo, monospace'

# Chart sizes, so a small chart in a two-column row and a full-width chart do
# not look like they came from two different applications.
CHART_SIZE = {
    "xs": 200,
    "sm": 240,
    "md": 288,
    "lg": 330,
    "xl": 380,
}

# Minimum height a horizontal-bar chart needs per row so a 20-row city ranking
# does not squash its labels.
BAR_ROW_MIN = 30

# Distinct, muted-enough hues for category/subcategory breakdowns. Ten
# categories in the dataset, so ten slots. Ordered so adjacent slots stay far
# apart, and all ten are legible on the dark canvas without glowing.
CATEGORICAL = [
    "#8B7CFF",  # violet
    "#22D3EE",  # cyan
    "#34D399",  # emerald
    "#FBBF24",  # amber
    "#F472B6",  # pink
    "#60A5FA",  # blue
    "#A3E635",  # lime
    "#FB923C",  # orange
    "#C084FC",  # light violet
    "#7C88AD",  # slate
]

STATUS_COLORS = {
    "Completed": PALETTE["success"],
    "Pending": PALETTE["warning"],
    "Cancelled": PALETTE["danger"],
    "Returned": PALETTE["returned"],
}

PAYMENT_STATUS_COLORS = {
    "Paid": PALETTE["success"],
    "Pending": PALETTE["warning"],
    "Failed": PALETTE["danger"],
    "Refunded": PALETTE["returned"],
}

# ---------------------------------------------------------------------------
# Dashboard chrome
# ---------------------------------------------------------------------------
APP_TITLE = "E-Commerce Sales Analytics"
# Set in title case because it is the sub-heading of the centred portfolio title
# in the header, not a sentence in running text.
APP_SUBTITLE = "Interactive Business Intelligence Dashboard"
APP_TAGLINE = "Sales &middot; Customers &middot; Products &middot; Payments"
# The sidebar carries a shorter identity than the page header, because it sits
# in a 272px column and has to survive on one line.
APP_SIDE_NAME = "E-Commerce Analytics"
APP_SIDE_SUB = "Sales Intelligence Dashboard"
DATASET_BADGE = "Synthetic dataset"

# Navigation order. Kept as plain (key, label) tuples because the page test
# walks this list and drives the sidebar radio by label.
PAGES = [
    ("overview", "Overview"),
    ("sales", "Sales Analysis"),
    ("products", "Products"),
    ("customers", "Customers"),
    ("orders", "Operations / Orders"),
    ("payments", "Payments"),
    ("insights", "Insights"),
]

# Per-page header copy. The subtitle is the one line that tells a reader what
# the page will answer, so it is kept to a single sentence.
PAGE_META = {
    "overview": (
        "Overview",
        "Interactive overview of sales, customers, products and operations.",
    ),
    "sales": (
        "Sales Analysis",
        "How sales are performing: trend, growth, contribution, basket and discounting.",
    ),
    "products": (
        "Products",
        "Catalogue performance - revenue leaders, volume leaders, profitability and discount bands.",
    ),
    "customers": (
        "Customers",
        "Reach, repeat behaviour, spend concentration and a transparent one-time/repeat split.",
    ),
    "orders": (
        "Operations / Orders",
        "Order flow, status mix, basket size and the searchable order-level record set.",
    ),
    "payments": (
        "Payments",
        "Method mix, payment outcomes, failure rates and the method-by-status heatmap.",
    ),
    "insights": (
        "Insights",
        "Findings computed live from the current selection, with the limits of the data stated.",
    ),
}

# Filter defaults. 'All' is represented by None / empty selection.
DEFAULT_TOP_N = 10
CACHE_TTL_REFERENCE = 3600   # reference lists change only when the data changes
CACHE_TTL_ANALYTICS = 300    # analytical queries, still fast enough to feel live
