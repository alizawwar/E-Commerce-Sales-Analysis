"""Render every dashboard page headlessly and fail on any exception.

This is the "does the app actually work" test. It runs the real
``dashboard/app.py`` through Streamlit's own test harness, so it exercises the
same code path a browser would: real MySQL queries, real Plotly figures, real
components. It then navigates to each page in turn and checks that none of them
raise.

It also drives the filter widgets the way a user would and confirms the visible
KPI text changes.

Run with::

    python scripts/test_dashboard_pages.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The Windows console defaults to a legacy code page that cannot encode the
# box-drawing and tick characters used in the report. Without this, printing a
# failure message that contains one raises UnicodeEncodeError and hides the real
# error behind a much more confusing one.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from streamlit.testing.v1 import AppTest  # noqa: E402

from dashboard.config import PAGES  # noqa: E402

APP = ROOT / "dashboard" / "app.py"
TIMEOUT = 300

GREEN, RED, BOLD, GREY, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[90m", "\033[0m"

failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)
    print(f"  {RED}FAIL{RESET}  {message}")


def ok(message: str, detail: str = "") -> None:
    suffix = f"  {GREY}{detail}{RESET}" if detail else ""
    print(f"  {GREEN}PASS{RESET}  {message}{suffix}")


def render(at: AppTest, label: str) -> bool:
    """Run the app and report whether it raised anything."""
    at.run(timeout=TIMEOUT)
    if at.exception:
        for exc in at.exception:
            fail(f"{label}: {exc.value}")
        return False
    ok(label)
    return True


def body_text(at: AppTest) -> str:
    """All text the app rendered, for substring assertions."""
    parts = [m.value for m in at.markdown]
    parts += [c.value for c in at.caption]
    parts += [str(w.value) for w in at.warning]
    return "\n".join(parts)


def _selector_lists(css: str) -> list[list[str]]:
    """Split a stylesheet into its rules and each rule's selector list.

    Depth-aware, so a comma inside a declaration value is not mistaken for a
    selector separator.
    """
    rules: list[list[str]] = []
    depth = 0
    start = 0
    for index, char in enumerate(css):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                rules.append(css[start:index].split(","))
    return rules


# ===========================================================================
# The design system, checked without a browser.
#
# components._stylesheet() is one long concatenated string rather than a .css
# file, so nothing validates it before it reaches the browser. These checks
# cover two classes of mistake that were both made and both of which failed
# silently - the page still rendered, it just rendered wrong.
#
#   * a joined selector list. "a, b" followed by ":hover" means `a` plus
#     `b:hover`, not `(a, b):hover`, and the same goes for a descendant part.
#     A rule written to flatten a table inside a card was therefore matching
#     every card and stripping the border, radius and shadow off all of them.
#   * an unbalanced or newline-bearing stylesheet. The stylesheet is injected
#     through st.markdown, so a newline here is the same hazard as indented
#     markup: st.markdown escapes it and the reader sees the CSS.
# ===========================================================================
def check_stylesheet() -> None:
    from dashboard import components

    css = components._stylesheet()

    if "\n" in css or "\r" in css:
        fail("stylesheet contains a newline, which st.markdown would render as a "
             f"code block ({css.count(chr(10))} found)")
    else:
        ok("stylesheet is a single line")

    if css.count("{") != css.count("}"):
        fail("stylesheet braces are unbalanced: "
             f"{css.count('{')} open vs {css.count('}')} close")
    else:
        ok("stylesheet braces are balanced", f"{css.count('{')} rules")

    rules = _selector_lists(css)
    blank = [rule for rule in rules if any(not s.strip() for s in rule)]
    if blank:
        fail(f"stylesheet has an empty selector in {blank[:2]}")
    else:
        ok("every selector in the stylesheet is non-empty", f"{len(rules)} rules")

    # The point of _panel(suffix) is that the suffix reaches *every* selector
    # in the group. This is the check that would have caught the real bug.
    for suffix in (":hover", "", " [data-testid='stDataFrame']"):
        group = [s.strip() for s in components._panel(suffix).split(",")]
        if suffix and not all(s.endswith(suffix) for s in group):
            fail(f"_panel({suffix!r}) did not apply the suffix to every "
                 f"selector: {group}")
            return
    ok("panel selectors carry their suffix on every entry",
       f"{len(components.PANEL_SELECTORS)} container selectors")

    # A var() that resolves to nothing is a *dropped declaration*, not an error:
    # the page still renders, it just renders in whatever colour was inherited.
    # The dark restyle shipped a rule for the active nav row, the filter chips
    # and the selected tab that all read --d-revenue-soft, a token that was
    # never published, so all three silently fell back to inherited white. Every
    # --d-* reference has to be a token the design system actually defines.
    import re

    referenced = set(re.findall(r"var\((--d-[a-z0-9-]+)\)", css))
    defined = set(re.findall(r"(--d-[a-z0-9-]+):", components._tokens_css()))
    undefined = sorted(referenced - defined)
    if undefined:
        fail(f"stylesheet references undefined design tokens: {undefined}")
    else:
        ok("every design token the stylesheet uses is defined",
           f"{len(referenced)} referenced, {len(defined)} defined")


# ===========================================================================
# No debug output reaches the page.
#
# A stack trace or a SQL statement in the middle of a business dashboard is
# noise the reader cannot act on. The app catches its own failures, shows one
# plain sentence, and writes the traceback to dashboard/dashboard.log - so the
# UI has no mechanism for showing one. error_panel is given no parameter that
# could carry a traceback, and st.code is not called anywhere in the package.
# Both are asserted here because both would otherwise be easy to reintroduce.
# ===========================================================================
def check_no_debug_output() -> None:
    import inspect

    from dashboard import components

    params = set(inspect.signature(components.error_panel).parameters)
    risky = params & {"detail", "traceback", "exc", "exception", "code"}
    if risky:
        fail(f"error_panel accepts a diagnostic parameter: {sorted(risky)}")
    else:
        ok("error_panel cannot render a traceback",
           "params: " + ", ".join(sorted(params - {"message"})))

    offenders = []
    for path in sorted((ROOT / "dashboard").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for needle in ("st.code(", "st.expander(", "traceback.format_exc()"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    if offenders:
        fail("debug output can reach the UI: " + "; ".join(offenders))
    else:
        ok("no st.code, st.expander or traceback.format_exc in the package")

    config = ROOT / ".streamlit" / "config.toml"
    if "showErrorDetails = true" in config.read_text(encoding="utf-8"):
        fail(".streamlit/config.toml enables Streamlit's stack-trace box")
    else:
        ok("Streamlit's exception box is suppressed")


# ===========================================================================
print(f"\n{BOLD}Design system{RESET}")
print("-" * 70)

check_stylesheet()
check_no_debug_output()

# ===========================================================================
print(f"\n{BOLD}Startup{RESET}")
print("-" * 70)

at = AppTest.from_file(str(APP), default_timeout=TIMEOUT)
if not render(at, "app starts and renders the default page"):
    print(f"\n{RED}Cannot continue: the app does not start.{RESET}")
    sys.exit(1)

# ---------------------------------------------------------------------------
print(f"\n{BOLD}Connection{RESET}")
print("-" * 70)

if at.sidebar.error:
    fail(f"sidebar reported a connection error: {[e.value for e in at.sidebar.error]}")
else:
    ok("no connection error in the sidebar")

# Phase 5 replaced the sidebar's `st.success` box with a styled connection
# badge (a sidebar markdown element), so the check reads that instead. The
# behaviour being validated is unchanged: the app must reach MySQL and say so
# where the reader can see it.
sidebar_html = "\n".join(m.value for m in at.sidebar.markdown)
if ('class="d-conn is-ok"' in sidebar_html
        and "Connected to ecommerce_sales_analysis" in sidebar_html):
    ok("connection status shown in the sidebar",
       "connected to ecommerce_sales_analysis")
else:
    fail("no successful connection badge shown in the sidebar")

text = body_text(at)
if "12,000 orders" in text:
    ok("dataset summary present in the sidebar", "12,000 orders")
else:
    fail("dataset summary missing from the sidebar")

# The headline figure must be the Phase 3 value, produced by a live query.
if "PKR 632.6M" in text or "632.6M" in text:
    ok("realised revenue card shows the Phase 3 value", "PKR 632.6M")
else:
    fail("realised revenue card does not show 632.6M")

if "31.03%" in text:
    ok("profit margin card shows the Phase 3 value", "31.03%")
else:
    fail("profit margin card does not show 31.03%")

# ---------------------------------------------------------------------------
print(f"\n{BOLD}Every page renders{RESET}")
print("-" * 70)

for key, label in PAGES:
    radio = at.sidebar.radio[0]
    if radio.value != label:
        radio.set_value(label)
    render(at, f"page: {label}")

    charts = len(at.get("plotly_chart"))
    tables = len(at.dataframe)
    if charts == 0:
        fail(f"{label} rendered no charts")
    if tables == 0:
        fail(f"{label} rendered no tables")
    if charts and tables:
        ok(f"{label} has content", f"{charts} charts, {tables} tables")

    # ------------------------------------------------------------------
    # Regression guard for the Phase 5 rendering bug.
    #
    # st.markdown runs CommonMark, where a blank line followed by four or more
    # spaces of indentation is an *indented code block*: the markup is escaped
    # and shown to the reader as literal source. The Phase 4 KPI grid was built
    # from indented multi-line f-strings, so the dashboard showed its own HTML.
    #
    # `Markdown.value` is the string that was handed to st.markdown, so the
    # risky pattern is visible here without needing a browser. components.
    # _markup() collapses every fragment onto one line, which removes it
    # structurally; this check makes sure nobody reintroduces it.
    offenders = [
        m.value[:90] for m in at.markdown
        if re.search(r"\n[ \t]{4,}\S", m.value)
    ]
    if offenders:
        fail(f"{label}: indented markdown would render as visible source code "
             f"({len(offenders)} block(s), first: {offenders[0]!r})")
    else:
        ok(f"{label} markup cannot render as a code block")

# ---------------------------------------------------------------------------
print(f"\n{BOLD}Filters drive the UI{RESET}")
print("-" * 70)

# Back to Overview, unfiltered.
at.sidebar.radio[0].set_value("Overview")
at.run(timeout=TIMEOUT)
baseline = body_text(at)

# Date range. The start bound has to be honoured as well as the end bound:
# an earlier version of the sidebar unpacked the tuple and then tested
# `isinstance(start, date)`, which is always true, so the chosen start date
# was silently discarded and the filter stayed on the full range.
date_input = at.sidebar.date_input[0]
if len(date_input.value) == 2:
    ok("date range widget initialised", f"{date_input.value[0]} to {date_input.value[1]}")
    # AppTest does not expose min_value/max_value, so use the bounds the widget
    # was initialised with (the full data window).
    lo, hi = date_input.value
    date_input.set_value((lo, lo))
    render(at, "date range narrows to a single day")
    narrowed = body_text(at)
    if "PKR 632.6M" in narrowed:
        fail("narrowing the date range did not reduce realised revenue")
    else:
        ok("date range start bound is honoured",
           "single-day scope no longer shows the full-period total")
    # Re-fetch: the handle above belongs to the previous run.
    at.sidebar.date_input[0].set_value((lo, hi))
    render(at, "date range restored to the full window")
    if "PKR 632.6M" not in body_text(at):
        fail("restoring the date range did not bring the total back")
    else:
        ok("restoring the date range returns the full-period total")
else:
    fail(f"unexpected date_input value: {date_input.value!r}")

# City multiselect.
#
# NOTE: AppTest rebuilds the element tree on every run, so a widget handle from
# an earlier run is stale. Every interaction below re-fetches the widget by its
# sidebar label immediately before setting it. Holding a handle across runs
# silently applies the value to the wrong element, which is a test bug that
# looks exactly like an application bug.
def choose(label: str, value: list[str]) -> bool:
    for widget in at.sidebar.multiselect:
        if widget.label == label:
            widget.set_value(value)
            return render(at, f"filter {label} = {', '.join(value)}")
    fail(f"no '{label}' multiselect in the sidebar")
    return False


ok("filter widgets present",
   ", ".join(w.label for w in at.sidebar.multiselect))

choose("City", ["Karachi"])
if "PKR 632.6M" in body_text(at):
    fail("city filter did not reduce realised revenue (still shows the full total)")
else:
    ok("city filter changed the metrics")
if "City: Karachi" in body_text(at):
    ok("active-filter chip shown", "City: Karachi")
else:
    fail("no filter chip rendered for the selected city")

# Category on top of the city filter -> the combined example from the brief.
choose("Category", ["Electronics"])
if "Category: Electronics" not in body_text(at):
    fail("category chip missing")
else:
    ok("combined city + category filters active")

# Status filter
choose("Order status", ["Completed"])
if "Status: Completed" not in body_text(at):
    fail("status chip missing")
else:
    ok("status filter chip shown")

# Payment method filter, on top of city + category + status. The label must be
# the real value from the database ("Cash on Delivery"), not a shorthand.
choose("Payment method", ["Cash on Delivery"])
if "Payment: Cash on Delivery" not in body_text(at):
    fail("payment chip missing")
else:
    ok("payment method filter chip shown")
if not at.exception:
    ok("four simultaneous filters render without error",
       "city + category + status + payment method")

# Reset
at.sidebar.button[0].click()
render(at, "reset all filters")
if "PKR 632.6M" in body_text(at):
    ok("reset restored the full-dataset figures", "PKR 632.6M")
else:
    fail("reset did not restore the default view")
for widget in at.sidebar.multiselect:
    if widget.label == "City" and widget.value:
        fail(f"reset left City = {widget.value}")
    if widget.label == "Order status" and len(widget.value) != 4:
        fail(f"reset left Order status = {widget.value}")

# ---------------------------------------------------------------------------
print(f"\n{BOLD}Empty state{RESET}")
print("-" * 70)

# A single day plus a city that has no orders that day must show a message, not
# a traceback.
for widget in at.sidebar.multiselect:
    if widget.label == "City":
        widget.set_value(["Karachi"])
at.sidebar.date_input[0].set_value((lo, lo))
at.run(timeout=TIMEOUT)
if at.exception:
    for exc in at.exception:
        fail(f"narrow filter raised: {exc.value}")
elif at.warning:
    ok("narrow filter shows a user-facing message", at.warning[0].value[:60])
else:
    ok("narrow filter rendered without error")

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
if failures:
    print(f"{RED}{BOLD}{len(failures)} page-level problem(s){RESET}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"{GREEN}{BOLD}All pages render, all filters work, no exceptions.{RESET}")
sys.exit(0)
