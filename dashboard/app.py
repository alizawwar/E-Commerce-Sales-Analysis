"""E-Commerce Analytics Dashboard - application entry point.

Run it with::

    python -m streamlit run dashboard/app.py

Architecture::

    MySQL (ecommerce_sales_analysis)
        -> dashboard/queries.py      parameterised SQL, cached
        -> dashboard/metrics.py     pure derivations (rates, margins, segments)
        -> dashboard/charts.py      Plotly figures + the chart theme
        -> dashboard/components.py  design system: shell, cards, panels, tables
        -> dashboard/views/*.py     one module per page
        -> this file                navigation, global filters, error handling

The filter widgets live in the sidebar and are applied on every rerun, so every
page reflects the same selection. The selection is also echoed above the
content in the filter bar, so the current scope is never hidden in a sidebar.
No figure is hardcoded anywhere.
"""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

# Allow `streamlit run dashboard/app.py` while still using package-relative
# imports inside the dashboard package.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from dashboard import components, queries  # noqa: E402
from dashboard.config import (  # noqa: E402
    APP_SIDE_NAME,
    APP_SIDE_SUB,
    APP_SUBTITLE,
    APP_TAGLINE,
    APP_TITLE,
    CACHE_TTL_REFERENCE,
    DATASET_BADGE,
    PAGES,
    PAGE_META,
)
from dashboard.database import DashboardDBError  # noqa: E402
from dashboard.utils import Filters  # noqa: E402
from dashboard.views import (  # noqa: E402
    customers, insights, orders, overview, payments, products, sales,
)

# database.py configures logging to dashboard/dashboard.log when it is imported
# (which the import above has already done), so this logger writes to the same
# file. Every traceback goes here instead of to the page.
log = logging.getLogger("dashboard.app")

RENDERERS = {
    "overview": overview.render,
    "sales": sales.render,
    "products": products.render,
    "customers": customers.render,
    "orders": orders.render,
    "payments": payments.render,
    "insights": insights.render,
}

# Used when the database has not been reached yet, so the date widget still has
# a sensible window before the first successful query.
FALLBACK_DATE_MIN = date(2024, 10, 1)
FALLBACK_DATE_MAX = date(2026, 9, 26)


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=f"{APP_TITLE} - Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "about": (
            f"{APP_TITLE} - interactive business intelligence dashboard built on the "
            "Phase 3 MySQL analytics database. Synthetic dataset, amounts in PKR."
        ),
        "Get help": None,
        "Report a bug": None,
    },
)
components.inject_styles()


# ---------------------------------------------------------------------------
# Sidebar: brand, navigation, filters, data source
# ---------------------------------------------------------------------------
def sidebar(reference: dict, connected: bool) -> tuple[str, Filters]:
    """Render the sidebar and return ``(page_key, filters)``."""
    st.sidebar.markdown(
        '<div class="d-side-brand"><span class="d-brand-mark"></span><span>'
        f'<div class="d-side-name">{components.esc(APP_SIDE_NAME)}</div>'
        f'<div class="d-side-tag">{APP_SIDE_SUB}</div></span></div>',
        unsafe_allow_html=True,
    )

    page = st.sidebar.radio(
        "Navigation",
        [label for _, label in PAGES],
        index=0,
        label_visibility="collapsed",
    )
    page_key = next(key for key, label in PAGES if label == page)

    st.sidebar.markdown('<div class="d-side-sep"></div>', unsafe_allow_html=True)

    if not connected:
        return page_key, Filters()

    # ------------------------------------------------------------- filters
    st.sidebar.markdown('<div class="d-side-group">Filters</div>',
                        unsafe_allow_html=True)

    date_min = reference.get("date_min") or FALLBACK_DATE_MIN
    date_max = reference.get("date_max") or FALLBACK_DATE_MAX
    if not isinstance(date_min, date):
        date_min = FALLBACK_DATE_MIN
    if not isinstance(date_max, date):
        date_max = FALLBACK_DATE_MAX

    # `date_input` returns a (start, end) tuple once both bounds are chosen, but
    # a single `date` while the user is still picking the second one. The
    # distinction has to be made on the *return value's* type: checking the
    # unpacked `start` with `isinstance(start, date)` is always true, and
    # quietly discards whatever the user actually selected.
    chosen = st.sidebar.date_input(
        "Date range",
        value=(date_min, date_max),
        min_value=date_min,
        max_value=date_max,
        format="YYYY-MM-DD",
        key="f_dates",
    )
    if isinstance(chosen, (tuple, list)) and len(chosen) == 2:
        start, end = chosen
    elif isinstance(chosen, date):
        # Only one bound chosen so far: keep the other at its default.
        start, end = chosen, date_max
    else:
        start, end = date_min, date_max
    if start > end:
        start, end = end, start

    cities = st.sidebar.multiselect("City", reference.get("cities", []), key="f_cities",
                                    placeholder="All cities")
    categories = st.sidebar.multiselect("Category", reference.get("categories", []),
                                        key="f_categories", placeholder="All categories")

    sub_options: list[str] = []
    if categories:
        for cat in categories:
            sub_options.extend(reference.get("subcategories_by_category", {}).get(cat, []))
        sub_options = sorted(set(sub_options))
    subcategories = st.sidebar.multiselect(
        "Subcategory", sub_options, key="f_subcategories",
        placeholder="All subcategories" if sub_options else "Pick a category first",
        disabled=not sub_options,
    )
    statuses = st.sidebar.multiselect("Order status", reference.get("statuses", []),
                                      default=reference.get("statuses", []),
                                      key="f_statuses", placeholder="All statuses")
    methods = st.sidebar.multiselect("Payment method", reference.get("payment_methods", []),
                                     key="f_methods", placeholder="All methods")

    # The reset has to run as a *callback*, not as an `if` on the button's
    # return value. A button below the widgets returns True during the same
    # script run in which those widgets were already instantiated, and
    # Streamlit refuses to let `session_state` be written to a key that belongs
    # to a live widget ("cannot be modified after the widget is instantiated").
    # Callbacks run *before* the next script pass, when the session is clear.
    st.sidebar.button(
        "Reset all filters", width="stretch", key="f_reset",
        on_click=components.reset_filter_widgets,
    )

    return page_key, Filters(
        date_from=start, date_to=end, cities=cities, categories=categories,
        subcategories=subcategories, statuses=statuses, payment_methods=methods,
    )


def sidebar_footer(ok: bool, message: str) -> None:
    """Connection state and dataset provenance, at the foot of the sidebar."""
    st.sidebar.markdown('<div class="d-side-sep"></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="d-side-group">Data source</div>',
                        unsafe_allow_html=True)
    components.connection_badge(ok, message)

    summary = queries.dataset_summary() if ok else None
    if not summary:
        return
    facts = [
        ("Orders", f"{summary['orders']:,}"),
        ("Order lines", f"{summary['order_lines']:,}"),
        ("Customers", f"{summary['customers']:,}"),
        ("Products", f"{summary['products']:,}"),
    ]
    rows = "".join(
        f'<div class="d-fact-row"><span>{label}</span><span>{value}</span></div>'
        for label, value in facts
    )
    st.sidebar.markdown(
        f'<div class="d-side-facts">{rows}'
        f"<div>{components.esc(summary['first_order'])} to "
        f"{components.esc(summary['last_order'])}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    # The sentence form of the same facts. It is the accessible reading of the
    # grid above and it is what makes the numbers quotable outside the app.
    st.sidebar.caption(
        f"{summary['orders']:,} orders · {summary['order_lines']:,} order lines · "
        f"{summary['customers']:,} customers · {summary['products']:,} products. "
        "MySQL database `ecommerce_sales_analysis`."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _connection_status() -> tuple[bool, str]:
    from dashboard.database import test_connection

    return test_connection()


@st.cache_data(ttl=CACHE_TTL_REFERENCE, show_spinner=False)
def _cached_connection_status() -> tuple[bool, str]:
    return _connection_status()


def _connection_help(message: str) -> None:
    """What to do when MySQL cannot be reached. No credentials, ever.

    ``message`` is the one-line summary built by ``database.test_connection()``.
    ``scripts/test_dashboard_failure_modes.py`` asserts it never contains the
    password or driver internals, which is why it is safe to show, and why no
    raw exception text is rendered alongside it.
    """
    st.error("The dashboard cannot reach MySQL, so it has no data to show.")
    st.markdown(
        "**What to check**\n\n"
        "1. Is the MySQL service running?\n"
        "2. Does a `.env` file exist in the project root? Copy the template and "
        "fill in `DB_USER` and `DB_PASSWORD`:\n\n"
        "   ```\n   copy .env.example .env\n   ```\n\n"
        "3. Has the Phase 3 database been loaded? Run `sql/01` through `sql/04` "
        "in order."
    )
    st.caption(f"{message} The full detail is in dashboard/dashboard.log.")


def main() -> None:
    components.topbar(APP_TITLE, APP_SUBTITLE, DATASET_BADGE)

    ok, message = _cached_connection_status()
    reference = queries.reference_data() if ok else {}
    page_key, filters = sidebar(reference, ok)
    sidebar_footer(ok, message)

    title, subtitle = PAGE_META.get(page_key, (APP_TITLE, APP_SUBTITLE))
    components.page_header(title, subtitle)

    if not ok:
        _connection_help(message)
        return

    components.filter_bar(filters)
    if not filters.statuses:
        st.warning(
            "No order status is selected, so no orders are in scope. Select at least "
            "one status in the sidebar.",
        )
        return

    try:
        with st.spinner("Loading sales data from MySQL..."):
            RENDERERS[page_key](filters)
    except DashboardDBError:
        # The failure is real and the reader is told what it is; the statement
        # and its parameters go to the log, never to the page.
        log.exception("Query failed while rendering %r", page_key)
        components.error_panel(
            "The dashboard could not complete a database query.",
            hint="Try clearing a filter. Technical detail is in "
                 "dashboard/dashboard.log.",
        )
    except Exception as exc:  # noqa: BLE001 - last-resort guard for the UI
        log.exception("Unhandled error while rendering %r", page_key)
        components.error_panel(
            "Something went wrong while building this page.",
            hint=f"Error type: {type(exc).__name__}. Technical detail is in "
                 "dashboard/dashboard.log.",
        )


if __name__ == "__main__":
    # Nothing should reach here - main() guards the page render - but if it
    # does, the reader gets one plain sentence and the traceback goes to the
    # log. Streamlit's own exception box is suppressed in
    # .streamlit/config.toml for the same reason.
    try:
        main()
    except Exception:  # noqa: BLE001
        log.exception("Unhandled error before the page render")
        st.error(
            "The dashboard could not start. The detail is in "
            "dashboard/dashboard.log."
        )
