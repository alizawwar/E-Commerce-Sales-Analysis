"""Reusable presentation components - the dashboard's design system.

Every visual primitive the pages use lives here: the app shell styling, the page
header, the filter strip, KPI cards, chart panels, callouts, finding cards,
tables, and the loading / empty / error states. Pages stay short because they
only arrange these pieces; they never invent their own markup.

WHY MARKUP IS RENDERED AS ONE LINE
-----------------------------------
``st.markdown`` runs Streamlit's CommonMark renderer, in which a blank line
followed by four or more spaces of indentation is an *indented code block* - the
text is escaped and shown to the reader as source code. The Phase 4 KPI cards
were built from indented multi-line f-strings, so the first card rendered and
every card after it appeared in the page as literal ``<div class="kpi-card">``
markup. :func:`_markup` collapses every fragment onto a single line, which
removes that failure mode structurally rather than by remembering not to
indent. ``scripts/test_dashboard_pages.py`` asserts no rendered markdown can
reintroduce it.

TABLES
------
Table values stay **numeric** with the unit in the column header
(``Revenue (PKR)``) rather than pre-formatted strings, so Streamlit sorts the
column numerically - sorting ``PKR 632,578,306`` as text would put 9 before 90.
"""

from __future__ import annotations

import contextlib
import html
from dataclasses import dataclass
from typing import Any, Iterator, Sequence

import pandas as pd
import streamlit as st

from .config import (
    BAR_ROW_MIN,
    CHART_SIZE,
    FONT_STACK,
    LAYOUT,
    PALETTE,
    SURFACE,
)
from .utils import Filters

# Widget keys owned by the global filters. Declared here rather than in app.py so
# the reset callback and the chip renderer that describe the same state live
# together.
FILTER_WIDGET_KEYS = (
    "f_dates", "f_cities", "f_categories", "f_subcategories", "f_statuses", "f_methods",
)

# Shared Plotly toolbar. Zoom, pan, box-select and download stay; the buttons
# that fight with a click-to-filter dashboard go.
CHART_CONFIG = {
    "displayModeBar": "hover",
    "displaylogo": False,
    "scrollZoom": False,
    "modeBarButtonsToRemove": [
        "select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
        "hoverClosestCartesian", "hoverCompareCartesian",
    ],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}

# The DOM a bordered Streamlit container produces, verified against the live app.
#
# Streamlit 1.64 renders `st.container(border=True)` as
#   [data-testid='stLayoutWrapper'] > [data-testid='stVerticalBlock']
# with the border on the inner vertical block. There is no
# `stVerticalBlockBorderWrapper` in this version, so a selector written for the
# older markup matches nothing and every panel silently falls back to
# Streamlit's default 1px translucent border.
#
# The child selector is load-bearing: `stLayoutWrapper` *also* wraps
# `st.columns`, and a column row holds a `stHorizontalBlock`, so requiring a
# `stVerticalBlock` child picks out the card containers and nothing else. The
# older test id is kept in the list so the same stylesheet still works if a
# future Streamlit restores it.
PANEL_SELECTORS = (
    "[data-testid='stLayoutWrapper']>[data-testid='stVerticalBlock']",
    "[data-testid='stVerticalBlockBorderWrapper']",
)


def _panel(suffix: str = "") -> str:
    """Selector list for the card containers, with ``suffix`` on every entry.

    Joining the selectors first and appending afterwards would be wrong: in
    ``a, b:hover`` the ``:hover`` belongs to ``b`` only, and in
    ``a, b table`` the descendant part belongs to ``b`` only. Either mistake
    silently turns a scoped rule into one that hits the real cards too, which
    is how a rule written to flatten a table inside a card ended up deleting the
    border, radius and shadow of every card on the page.
    """
    return ",".join(f"{selector}{suffix}" for selector in PANEL_SELECTORS)


# ---------------------------------------------------------------------------
# Markup helpers
# ---------------------------------------------------------------------------
def esc(value: Any) -> str:
    """HTML-escape any value for safe interpolation into a fragment."""
    return html.escape("" if value is None else str(value), quote=True)


def _markup(fragment: str, container: Any = None) -> None:
    """Emit one HTML fragment as a single, single-line Streamlit markdown block.

    Collapsing to one line is what makes indented HTML safe: there is no blank
    line for CommonMark to turn into an indented code block, and no leading
    whitespace for it to read as one.

    ``container`` is an optional ``DeltaGenerator`` (typically ``st.sidebar``)
    for the few fragments that belong somewhere other than the main body.
    """
    target = container if container is not None else st
    target.markdown(" ".join(fragment.split()), unsafe_allow_html=True)


def _tokens_css() -> str:
    """Publish the design tokens from config as CSS custom properties."""
    lines = [":root{"]
    for key, value in SURFACE.items():
        name = "--d-" + key.replace("_", "-")
        lines.append(f"{name}:{value};")
    for key, value in LAYOUT.items():
        name = "--d-" + key.replace("_", "-")
        lines.append(f"{name}:{value};")
    for name, value in (
        # Palette hues are published too, not just the semantic status colours.
        # Series colours and accent-tinted text (chips, code, the active tab,
        # the active nav row) have to be the *same* violet, or those tint rules
        # silently fall back to an inherited colour: a var() that resolves to
        # nothing is a dropped declaration, not a visible error.
        ("--d-revenue", PALETTE["revenue"]),
        ("--d-revenue-soft", PALETTE["revenue_soft"]),
        ("--d-profit", PALETTE["profit"]),
        ("--d-profit-soft", PALETTE["profit_soft"]),
        ("--d-good", PALETTE["success"]),
        ("--d-warn", PALETTE["warning"]),
        ("--d-bad", PALETTE["danger"]),
        ("--d-returned", PALETTE["returned"]),
        ("--d-neutral", PALETTE["neutral"]),
        ("--d-font", FONT_STACK),
        # Flat tints for the note / alert / status blocks. They are built from
        # the same violet the rest of the UI uses rather than from a second
        # hue system, so a dark surface never has to fight a colour that was
        # chosen for a light one.
        ("--d-tint-accent", "rgba(139,124,255,0.11)"),
        ("--d-tint-warn", "rgba(251,191,36,0.11)"),
        ("--d-tint-bad", "rgba(251,113,133,0.11)"),
        ("--d-tint-good", "rgba(52,211,153,0.11)"),
        ("--d-tint-line", "rgba(139,124,255,0.32)"),
        ("--d-hi", "rgba(255,255,255,0.06)"),
    ):
        lines.append(f"{name}:{value};")
    lines.append("}")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Global styling
# ---------------------------------------------------------------------------
def _stylesheet() -> str:
    """The single stylesheet for the application.

    Written without blank lines: a blank line followed by indented text inside
    ``st.markdown`` is what produced the visible-source-code bug, so the
    stylesheet never relies on that being safe.
    """
    # Descendant parts of the card rules, kept as names so they are handed to
    # _panel() rather than pasted after a joined selector list - see _panel().
    inner_block = " [data-testid='stVerticalBlock']"
    frame = " [data-testid='stDataFrame']"
    frame_radius = " [data-testid='stDataFrameResizable']>div:first-child"
    return (
        # ---------------------------------------------------------- tokens
        _tokens_css()
        # ------------------------------------------------------- app shell
        + "[data-testid='stAppViewContainer']>.main,"
        + "[data-testid='stMain']>.block-container{padding-top:0;}"
        + ".stApp,"
        + "body{background:var(--d-canvas);font-family:var(--d-font);}"
        + ".block-container{padding:1.35rem 2rem 5rem 2rem;"
        + "max-width:var(--d-page-max-width);}"
        + "[data-testid='stHeader']{background:transparent;height:0;}"
        + "[data-testid='stToolbar']{right:0.5rem;}"
        + "#MainMenu,"
        + "footer{visibility:hidden;height:0;}"
        # Streamlit styles headings through an emotion class scoped as
        # `.st-emotion-cache-xxxx h1`, which is *more* specific than a bare
        # `.d-page-title`. These selectors carry two class hooks so the design
        # system's sizes and type actually win instead of being overridden.
        + ".stMarkdown h1,.stMarkdown h2,.stMarkdown h3,.stMarkdown h4,"
        + ".stMarkdown h5,.stMarkdown h6,.stMarkdown p,.stMarkdown li,"
        + ".stMarkdown label,.stMarkdown span,.stMarkdown div{"
        + "font-family:var(--d-font);letter-spacing:-0.005em;}"
        + "h1,h2,h3,h4,h5,h6,p,li,label,span,div{"
        + "font-family:var(--d-font);letter-spacing:-0.005em;}"
        + "p{margin:0;line-height:1.55;}"
        + "code{font-family:'Cascadia Mono',Consolas,monospace;font-size:0.86em;"
        + "background:var(--d-inset);color:var(--d-revenue-soft);"
        + "padding:0.06rem 0.3rem;border-radius:4px;}"
        + "hr{margin:1.4rem 0;border-color:var(--d-border);}"
        + "::selection{background:rgba(139,124,255,0.32);}"
        + "*:focus-visible{outline:2px solid var(--d-accent);outline-offset:2px;}"
        # ------------------------------------------------------- top bar
        # The header is a centred portfolio title rather than a slim app bar:
        # the project name is the largest type on the page and sits on the true
        # centre line, with the sub-heading directly beneath it. `.d-hero` is
        # given symmetric side padding so a centred title can never slide under
        # the badge in the corner, and the badge is out of flow so it can never
        # shift the title off centre either.
        + ".d-topbar{position:relative;display:flex;justify-content:center;"
        + "align-items:center;padding:0.1rem 0 0.85rem;"
        + "border-bottom:1px solid var(--d-border);margin-bottom:1.05rem;}"
        + ".d-hero{text-align:center;min-width:0;padding:0 6.5rem;}"
        # `inline-block`, not `inline-flex`. A flex row is centred as a *unit*,
        # so a 32px mark sitting in front of the title shifts the title text
        # right by half of (mark + gap). Taking the mark out of flow lets the
        # title element itself sit on the true centre line.
        + ".d-hero-row{position:relative;display:inline-block;max-width:100%;}"
        # Two class hooks, because Streamlit styles headings through an emotion
        # class scoped as `.stMarkdown h1` (see the note above).
        + ".d-topbar h1.d-hero-title{font-size:2.1rem;font-weight:700;"
        + "color:var(--d-text);line-height:1.1;margin:0;padding:0;"
        + "letter-spacing:-0.03em;display:inline-block;vertical-align:middle;}"
        + ".d-hero-sub{font-size:0.875rem;font-weight:500;"
        + "color:var(--d-text-soft);margin-top:0.36rem;letter-spacing:0.055em;"
        + "line-height:1.35;}"
        + ".d-brand-mark{width:26px;height:26px;border-radius:7px;flex:0 0 auto;"
        + "background:linear-gradient(140deg,var(--d-accent),var(--d-accent-2));"
        + "box-shadow:0 2px 10px rgba(91,79,214,0.45);position:relative;}"
        + ".d-brand-mark::after{content:'';position:absolute;inset:7px 7px auto 7px;"
        + "height:3px;border-radius:2px;background:rgba(255,255,255,.92);"
        + "box-shadow:0 6px 0 rgba(255,255,255,.55);}"
        # Sized up here only, for the hero, and out of flow so the centred
        # title is not measured against it. The sidebar reuses the same mark at
        # its own scale, and this change is meant to leave the sidebar alone.
        + ".d-hero-row .d-brand-mark{position:absolute;top:50%;"
        + "transform:translateY(-50%);right:calc(100% + 0.75rem);"
        + "width:32px;height:32px;border-radius:9px;"
        + "box-shadow:0 3px 14px rgba(91,79,214,0.55);}"
        + ".d-hero-row .d-brand-mark::after{inset:9px 9px auto 9px;}"
        + ".d-badge{position:absolute;top:0.1rem;right:0;"
        + "display:inline-flex;align-items:center;gap:0.35rem;"
        + "font-size:0.68rem;font-weight:600;letter-spacing:0.03em;"
        + "color:var(--d-warn);background:var(--d-tint-warn);"
        + "border:1px solid rgba(251,191,36,0.3);"
        + "border-radius:var(--d-radius-pill);padding:0.2rem 0.6rem;"
        + "white-space:nowrap;}"
        + ".d-badge i{width:6px;height:6px;border-radius:50%;background:var(--d-warn);"
        + "display:inline-block;font-style:normal;}"
        # ----------------------------------------------------- page header
        + ".d-page-head{display:flex;align-items:flex-end;justify-content:space-between;"
        + "gap:1.2rem;flex-wrap:wrap;margin:0 0 0.9rem 0;}"
        + ".d-page-head h2.d-page-title{font-size:1.62rem;font-weight:680;"
        + "color:var(--d-text);line-height:1.16;margin:0;padding:0;"
        + "letter-spacing:-0.022em;}"
        + ".d-page-sub{font-size:0.855rem;color:var(--d-text-soft);margin-top:0.24rem;"
        + "max-width:74ch;line-height:1.5;}"
        + ".d-page-meta{display:flex;align-items:center;gap:0.45rem;flex-wrap:wrap;"
        + "padding-bottom:0.15rem;}"
        # ------------------------------------------------------ filter bar
        + ".d-filterbar{display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;"
        + "background:var(--d-card);border:1px solid var(--d-border);"
        + "border-radius:var(--d-radius);box-shadow:var(--d-shadow);"
        + "padding:0.5rem 0.7rem;margin:0 0 1rem 0;}"
        + ".d-filterbar-label{font-size:0.655rem;font-weight:660;letter-spacing:0.09em;"
        + "text-transform:uppercase;color:var(--d-text-muted);white-space:nowrap;"
        + "padding-right:0.15rem;}"
        + ".d-chip{display:inline-flex;align-items:center;gap:0.3rem;font-size:0.72rem;"
        + "font-weight:550;color:var(--d-revenue-soft);"
        + "background:var(--d-tint-accent);"
        + "border:1px solid var(--d-tint-line);border-radius:"
        + "var(--d-radius-pill);padding:0.16rem 0.55rem;line-height:1.5;}"
        + ".d-chip b{font-weight:660;}"
        + ".d-chip.is-neutral{color:var(--d-text-soft);background:var(--d-card-alt);"
        + "border-color:var(--d-border);}"
        + ".d-chip-dot{width:5px;height:5px;border-radius:50%;background:var(--d-accent);}"
        + ".d-filterbar-end{margin-left:auto;display:flex;align-items:center;gap:0.5rem;}"
        + ".d-filterbar-count{font-size:0.7rem;color:var(--d-text-muted);white-space:nowrap;}"
        # ---------------------------------------------------- section heads
        # Section headings get a gradient rule rather than a solid tick: on a
        # dark canvas a solid bar is the brightest thing in the gap between two
        # card rows and pulls the eye away from the numbers.
        + ".d-section{display:flex;align-items:baseline;gap:0.5rem;margin:1.45rem 0 0.1rem 0;}"
        + ".d-section::before{content:'';width:3px;height:0.95em;border-radius:2px;"
        + "flex:0 0 auto;transform:translateY(1px);"
        + "background:linear-gradient(180deg,var(--d-accent),var(--d-accent-2));}"
        + ".d-section-t{font-size:1rem;font-weight:650;color:var(--d-text);"
        + "letter-spacing:-0.012em;line-height:1.3;}"
        + ".d-section-s{font-size:0.78rem;color:var(--d-text-muted);margin:0.06rem 0 0.55rem 0;"
        + "padding-left:0.68rem;max-width:88ch;line-height:1.5;}"
        + ".d-section-sm{margin:0.1rem 0 0.4rem 0;}"
        + ".d-section-sm .d-section-t{font-size:0.845rem;font-weight:640;}"
        + ".d-section-sm .d-section-s{font-size:0.725rem;padding-left:0.68rem;"
        + "margin:0.02rem 0 0.4rem 0;}"
        # --------------------------------------------------------- KPI cards
        # The column count is decided per grid by kpi_grid() and published as
        # --d-kpi-cols, so a band of eight cards is one clean two-row block on a
        # wide screen instead of three-plus-a-gap. The media queries below step
        # the count down as the content area narrows.
        #
        # The accent is a short vertical rule on the leading edge rather than a
        # full fill: eight saturated cards in a row read as a wall of colour,
        # while a hairline keeps the metric hierarchy and lets the number carry
        # the emphasis.
        + ".d-kpi-grid{display:grid;gap:var(--d-gutter);grid-template-columns:"
        + "repeat(var(--d-kpi-cols,3),minmax(0,1fr));margin:0 0 0.15rem 0;}"
        + ".d-kpi{position:relative;background:var(--d-card);"
        + "border:1px solid var(--d-border);border-radius:"
        + "var(--d-radius);border-left:2px solid var(--kpi,var(--d-accent));"
        + "box-shadow:var(--d-shadow);padding:0.6rem 0.75rem 0.65rem 0.75rem;"
        + "min-width:0;overflow:hidden;"
        + "transition:border-color .16s ease,box-shadow .16s ease;}"
        + ".d-kpi:hover{border-color:var(--kpi,var(--d-accent));"
        + "box-shadow:var(--d-shadow-lift);}"
        + ".d-kpi::after{content:'';position:absolute;left:0;right:0;top:0;height:1px;"
        + "background:linear-gradient(90deg,var(--kpi,var(--d-accent)),transparent 72%);"
        + "opacity:0;transition:opacity .16s ease;}"
        + ".d-kpi:hover::after{opacity:0.5;}"
        + ".d-kpi-label{font-size:0.635rem;font-weight:660;letter-spacing:0.08em;"
        + "text-transform:uppercase;color:var(--d-text-muted);line-height:1.35;}"
        + ".d-kpi-value{font-size:1.36rem;font-weight:680;color:var(--d-text);"
        + "line-height:1.15;margin-top:0.28rem;letter-spacing:-0.024em;"
        + "font-variant-numeric:tabular-nums;white-space:nowrap;"
        + "overflow:hidden;text-overflow:ellipsis;}"
        + ".d-kpi-value.sm{font-size:1.04rem;white-space:normal;line-height:1.25;}"
        + ".d-kpi-hint{font-size:0.705rem;color:var(--d-text-muted);margin-top:0.26rem;"
        + "line-height:1.4;}"
        + ".d-kpi-hint .up{color:var(--d-good);font-weight:640;}"
        + ".d-kpi-hint .down{color:var(--d-bad);font-weight:640;}"
        # ------------------------------------------------------ chart panels
        + f"{_panel()}{{background:var(--d-card);"
        + "border:1px solid var(--d-border);border-radius:"
        + "var(--d-radius);box-shadow:var(--d-shadow);"
        + "padding:0.85rem 0.95rem 0.7rem;}"
        + f"{_panel(':hover')}{{box-shadow:var(--d-shadow-lift);}}"
        + f"{_panel(inner_block)}{{gap:0.45rem;}}"
        # A table inside a card is flush with it; a table on its own keeps the
        # card treatment from the stDataFrame rule further down. Either way
        # there is exactly one border around the data.
        + f"{_panel(frame)}{{border:0;box-shadow:none;background:transparent;}}"
        + f"{_panel(frame_radius)}{{border-radius:0;}}"
        # --------------------------------------------------------- callouts
        + ".d-note{display:flex;gap:0.55rem;align-items:flex-start;font-size:0.775rem;"
        + "color:var(--d-text-soft);background:var(--d-card-alt);"
        + "border:1px solid var(--d-border);border-left:2px solid var(--d-neutral);"
        + "border-radius:var(--d-radius-sm);padding:0.55rem 0.72rem;"
        + "margin:0.4rem 0 0.75rem 0;line-height:1.55;}"
        + ".d-note b{color:var(--d-text);font-weight:640;}"
        + ".d-note.info{border-left-color:var(--d-accent);"
        + "background:var(--d-tint-accent);border-color:var(--d-tint-line);}"
        + ".d-note.warn{border-left-color:var(--d-warn);"
        + "background:var(--d-tint-warn);border-color:rgba(251,191,36,0.28);}"
        + ".d-note b.tone-warn{color:var(--d-warn);}"
        + ".d-note b.tone-good{color:var(--d-good);}"
        + ".d-note b.tone-bad{color:var(--d-bad);}"
        + ".d-note-tag{flex:0 0 auto;font-size:0.62rem;font-weight:700;letter-spacing:0.07em;"
        + "text-transform:uppercase;color:var(--d-text-muted);"
        + "border:1px solid var(--d-border);"
        + "border-radius:5px;padding:0.1rem 0.32rem;background:var(--d-card-alt);margin-top:1px;}"
        # ---------------------------------------------------- finding cards
        + ".d-find{background:var(--d-card);border:1px solid var(--d-border);"
        + "border-radius:"
        + "var(--d-radius);box-shadow:var(--d-shadow);"
        + "border-left:2px solid var(--kpi,var(--d-accent));padding:0.72rem 0.85rem;"
        + "min-width:0;}"
        + ".d-find-label{font-size:0.645rem;font-weight:660;letter-spacing:0.08em;"
        + "text-transform:uppercase;color:var(--d-text-muted);}"
        + ".d-find-value{font-size:1.12rem;font-weight:660;color:var(--d-text);"
        + "line-height:1.28;margin-top:0.22rem;letter-spacing:-0.016em;"
        + "font-variant-numeric:tabular-nums;}"
        + ".d-find-text{font-size:0.775rem;color:var(--d-text-soft);margin-top:0.3rem;"
        + "line-height:1.5;}"
        + ".d-find-text b{color:var(--d-text);font-weight:620;}"
        # --------------------------------------------------------- bullets
        + ".d-bullets{background:var(--d-card);border:1px solid var(--d-border);"
        + "border-radius:var(--d-radius);box-shadow:var(--d-shadow);"
        + "padding:0.85rem 0.95rem 0.9rem 0.95rem;}"
        + ".d-bullets ul{list-style:none;margin:0;padding:0;}"
        + ".d-bullets li{position:relative;padding-left:1.05rem;margin-bottom:0.42rem;"
        + "font-size:0.795rem;color:var(--d-text-soft);line-height:1.55;}"
        + ".d-bullets li:last-child{margin-bottom:0;}"
        + ".d-bullets li::before{content:'';position:absolute;left:0.05rem;top:0.56em;"
        + "width:5px;height:5px;border-radius:50%;background:var(--d-accent);opacity:.8;}"
        + ".d-bullets b{color:var(--d-text);font-weight:640;}"
        # ---------------------------------------------------------- sidebar
        + "section[data-testid='stSidebar']{background:var(--d-sidebar);"
        + "border-right:1px solid var(--d-border);width:"
        + "var(--d-sidebar-width)!important;min-width:0;}"
        + "section[data-testid='stSidebar'] .block-container{padding:0.9rem 0.85rem 2.5rem;}"
        + "section[data-testid='stSidebar'] [data-testid='stSidebarContent']>"
        + "[data-testid='stVerticalBlock']{gap:0.32rem;}"
        + ".d-side-brand{display:flex;gap:0.6rem;align-items:flex-start;"
        + "padding:0.1rem 0.15rem 0.7rem 0.15rem;}"
        + ".d-side-name{font-size:0.95rem;font-weight:680;color:var(--d-text);"
        + "line-height:1.22;letter-spacing:-0.016em;}"
        + ".d-side-tag{font-size:0.695rem;color:var(--d-text-muted);margin-top:0.14rem;"
        + "line-height:1.4;}"
        + ".d-side-group{font-size:0.62rem;font-weight:680;letter-spacing:0.11em;"
        + "text-transform:uppercase;color:var(--d-text-muted);margin:0.8rem 0 0.15rem;}"
        + ".d-side-sep{height:1px;background:var(--d-border);margin:0.7rem 0 0.1rem;}"
        + ".d-side-facts{font-size:0.71rem;color:var(--d-text-muted);line-height:1.65;}"
        + ".d-side-facts b{color:var(--d-text-soft);font-weight:620;}"
        + ".d-side-facts .d-fact-row{display:flex;justify-content:space-between;gap:0.5rem;}"
        + ".d-side-facts .d-fact-row span:last-child{color:var(--d-text-soft);"
        + "font-variant-numeric:tabular-nums;}"
        + ".d-conn{display:flex;align-items:center;gap:0.4rem;font-size:0.715rem;"
        + "font-weight:560;margin:0.15rem 0 0.35rem;}"
        + ".d-conn i{width:7px;height:7px;border-radius:50%;flex:0 0 auto;"
        + "background:var(--d-good);box-shadow:0 0 0 3px rgba(52,211,153,0.16);"
        + "font-style:normal;}"
        + ".d-conn.is-bad i{background:var(--d-bad);"
        + "box-shadow:0 0 0 3px rgba(251,113,133,0.16);}"
        + ".d-conn.is-bad{color:var(--d-bad);}"
        + ".d-conn.is-ok{color:var(--d-good);}"
        # sidebar nav radio -> a nav list
        + "section[data-testid='stSidebar'] [data-testid='stRadioGroup']{gap:1px;}"
        + "section[data-testid='stSidebar'] [data-testid='stRadioOption']{"
        + "border-radius:var(--d-radius-sm);padding:0.38rem 0.5rem;"
        + "border-left:2px solid transparent;transition:background .13s ease;}"
        + "section[data-testid='stSidebar'] [data-testid='stRadioOption']:hover{"
        + "background:var(--d-card);}"
        + "section[data-testid='stSidebar'] "
        + "label[data-testid='stRadioOption']:has(input:checked){"
        + "background:var(--d-tint-accent);border-left-color:var(--d-accent);}"
        + "section[data-testid='stSidebar'] [data-testid='stRadioOption'] p{"
        + "font-size:0.8rem;font-weight:560;color:var(--d-text-muted);line-height:1.3;}"
        + "section[data-testid='stSidebar'] "
        + "label[data-testid='stRadioOption']:has(input:checked) p{"
        + "font-weight:650;color:var(--d-revenue-soft);}"
        + "section[data-testid='stSidebar'] [data-testid='stRadioOption'] "
        + "span:first-child{width:0;overflow:hidden;}"
        + "section[data-testid='stSidebar'] [data-testid='stRadioOption'] "
        + "div[data-testid='stMarkdownContainer'] p{padding:0;}"
        # sidebar inputs
        + "section[data-testid='stSidebar'] label[data-testid='stWidgetLabel'] p,"
        + "[data-testid='stWidgetLabel'] p{font-size:0.755rem;font-weight:560;"
        + "color:var(--d-text-soft);}"
        + "section[data-testid='stSidebar'] [data-testid='stDateInput'] input,"
        + "section[data-testid='stSidebar'] [data-baseweb='input']{"
        + "font-size:0.77rem;border-radius:var(--d-radius-sm)!important;"
        + "background:var(--d-card)!important;color:var(--d-text)!important;"
        + "border-color:var(--d-border)!important;}"
        + "[data-testid='stWidgetLabel'] p{margin-bottom:0.15rem;}"
        + "[data-testid='stWidgetLabel'] svg{margin-top:-2px;}"
        + "section[data-testid='stSidebar'] hr{margin:0.6rem 0;border-color:"
        + "var(--d-border);}"
        # Streamlit 1.64 renders the date range through react-aria and the five
        # category filters as a styled button, and neither paints a background
        # or a border of its own - the theme's secondaryBackground only shows
        # through on some of them. Without this the whole filter column reads as
        # floating text rather than as controls, so the field chrome is stated
        # once here and both widget families get it.
        + "section[data-testid='stSidebar'] [data-testid='stDateInputField'],"
        + "section[data-testid='stSidebar'] [data-testid='stMultiSelect'] > div{"
        + "background:var(--d-card);border:1px solid var(--d-border);"
        + "border-radius:var(--d-radius-sm);min-height:2.15rem;}"
        + "section[data-testid='stSidebar'] [data-testid='stDateInputField']"
        + "{padding:0.42rem 0.55rem;}"
        # react-aria keeps its real <input>s off-screen at -1,-1; the visible
        # segments are the styled wrapper above, so the inputs themselves are
        # left un-boxed rather than given a second border.
        + "section[data-testid='stSidebar'] [data-testid='stDateInput'] input{"
        + "font-size:0.77rem;background:transparent!important;"
        + "border:0 solid transparent!important;color:var(--d-text)!important;"
        + "border-radius:0!important;}"
        + "section[data-testid='stSidebar'] [data-testid='stMultiSelect'] p"
        + "{font-size:0.77rem;color:var(--d-text-soft);line-height:1.4;margin:0;}"
        # ---------------------------------------------------------- buttons
        + ".stButton>button,"
        + ".stDownloadButton>button{font-size:0.78rem;font-weight:580;"
        + "border-radius:var(--d-radius-sm);border-color:var(--d-border);"
        + "color:var(--d-text);background:var(--d-card);"
        + "box-shadow:none;min-height:2.05rem;padding:0.2rem 0.7rem;"
        + "transition:border-color .14s ease,background .14s ease;}"
        + ".stButton>button:hover{border-color:var(--d-accent);color:var(--d-text);"
        + "background:var(--d-card-alt);}"
        + ".stButton>button[kind='primary']{background:var(--d-accent);"
        + "border-color:var(--d-accent);color:#fff;}"
        + ".stButton>button[kind='primary']:hover{background:#9E91FF;"
        + "border-color:#9E91FF;color:#fff;}"
        + ".stButton>button:disabled{opacity:.45;}"
        + ".stButton>button:focus-visible{outline:2px solid var(--d-accent);"
        + "outline-offset:1px;}"
        # ----------------------------------------------------------- tables
        + "[data-testid='stDataFrame']{border:1px solid var(--d-border);"
        + "border-radius:var(--d-radius-sm);overflow:hidden;box-shadow:var(--d-shadow);"
        + "background:var(--d-card);}"
        + "[data-testid='stDataFrame'] [role='columnheader']"
        + "{font-size:0.745rem;}"
        + "[data-testid='stDataFrameResizable']>div:first-child{border-radius:"
        + "var(--d-radius-sm);}"
        + "[data-testid='stDataFrame'] [data-testid='stDataFrameToolbar']"
        + "{border-bottom:1px solid var(--d-border);}"
        # ------------------------------------------------------------- tabs
        # Streamlit 1.64 renders a tab as div[data-testid='stTab'][role='tab']
        # and no longer emits the data-baseweb attributes the Phase 4 selectors
        # used, so those rules matched nothing and the strip kept Streamlit's
        # 14px full-bright default. Selected here against the real DOM.
        + ".stTabs [role='tablist']{gap:0.1rem;"
        + "border-bottom:1px solid var(--d-border);}"
        + ".stTabs [data-testid='stTab']{font-size:0.8rem;font-weight:580;"
        + "padding:0.3rem 0.68rem;color:var(--d-text-muted);"
        + "border-radius:var(--d-radius-sm) var(--d-radius-sm) 0 0;"
        + "transition:color .14s ease,background .14s ease;}"
        + ".stTabs [data-testid='stTab']:hover{color:var(--d-text-soft);"
        + "background:var(--d-card-alt);}"
        + ".stTabs [data-testid='stTab'][aria-selected='true']"
        + "{color:var(--d-revenue-soft);font-weight:650;background:transparent;}"
        # ---------------------------------------------------------- alerts
        + ".stAlert{border-radius:var(--d-radius-sm);padding:0.5rem 0.75rem;"
        + "font-size:0.785rem;border:1px solid var(--d-border);}"
        + ".stAlert p{line-height:1.55;}"
        + "[data-testid='stAlert'] [data-testid='stMarkdownContainer'] p{color:inherit;}"
        + ".stAlert[data-baseweb='kind'='success']{background:var(--d-tint-good);"
        + "border-color:rgba(52,211,153,0.28);color:#6EE7B7;}"
        + ".stAlert[data-baseweb='kind'='info']{background:var(--d-tint-accent);"
        + "border-color:var(--d-tint-line);color:#C4BDFF;}"
        + ".stAlert[data-baseweb='kind'='warning']{background:var(--d-tint-warn);"
        + "border-color:rgba(251,191,36,0.28);color:#FCD34D;}"
        + ".stAlert[data-baseweb='kind'='error']{background:var(--d-tint-bad);"
        + "border-color:rgba(251,113,133,0.28);color:#FDA4AF;}"
        + "[data-testid='stException']{border-radius:var(--d-radius-sm);}"
        + "details summary{cursor:pointer;color:var(--d-text-soft);}"
        + "details{border:1px solid var(--d-border);border-radius:"
        + "var(--d-radius-sm);padding:0.35rem 0.6rem;background:var(--d-card-alt);}"
        + "details pre{font-size:0.72rem;line-height:1.5;white-space:pre-wrap;}"
        # ------------------------------------------------------- misc / text
        + "[data-testid='stCaptionContainer'] p,"
        + "stCaption{font-size:0.735rem;color:var(--d-text-muted);line-height:1.5;}"
        + ".d-muted{color:var(--d-text-muted);}"
        + "[data-testid='stSpinner'] i{border-top-color:var(--d-accent);}"
        + "[data-testid='stSlider'] [data-baseweb='thumb']"
        + "{border-color:var(--d-accent);}"
        + "::-webkit-scrollbar{width:9px;height:9px;}"
        + "::-webkit-scrollbar-track{background:transparent;}"
        + "::-webkit-scrollbar-thumb{background:#3A3560;border-radius:6px;"
        + "border:2px solid transparent;background-clip:content-box;}"
        + "::-webkit-scrollbar-thumb:hover{background:#4E4780;background-clip:content-box;}"
        # ------------------------------------------------------- responsive
        # min() is allowed wherever repeat() takes an integer, so a band that
        # asked for five columns asks for three (then two) as space runs out,
        # without a second column count to keep in sync.
        + "@media (max-width:1560px){"
        + ".d-kpi-grid{grid-template-columns:"
        + "repeat(min(var(--d-kpi-cols,3),4),minmax(0,1fr));}"
        + "}"
        + "@media (max-width:1280px){"
        + ".d-kpi-grid{grid-template-columns:"
        + "repeat(min(var(--d-kpi-cols,3),3),minmax(0,1fr));}"
        + ".d-page-head h2.d-page-title{font-size:1.5rem;}"
        + ".d-kpi-value{font-size:1.28rem;}"
        # The hero keeps its own step: 2.1rem is sized for a wide main column,
        # and `.d-hero` side padding shrinks in step so the centred title
        # clears the badge on the way down.
        + ".d-hero{padding:0 4.5rem;}"
        + ".d-topbar h1.d-hero-title{font-size:1.78rem;}"
        + "}"
        + "@media (max-width:1000px){"
        + ".d-kpi-grid{grid-template-columns:"
        + "repeat(min(var(--d-kpi-cols,3),2),minmax(0,1fr));}"
        + ".block-container{padding:1rem 1.1rem 4rem;}"
        + ".d-page-head{margin-bottom:0.75rem;}"
        + ".d-filterbar-end{margin-left:0;width:100%;}"
        + ".d-filterbar{row-gap:0.4rem;}"
        + ".d-hero{padding:0 0.25rem;}"
        + ".d-topbar h1.d-hero-title{font-size:1.35rem;}"
        + ".d-hero-sub{font-size:0.74rem;letter-spacing:0.04em;margin-top:0.26rem;}"
        # Under ~1000px the corner no longer has room beside a centred title,
        # so the badge drops below it and stays centred. Still visible, and the
        # title stays genuinely centred rather than merely nudged.
        + ".d-topbar{flex-direction:column;gap:0.5rem;padding-top:0;"
        + "padding-bottom:0.7rem;}"
        + ".d-badge{position:static;order:2;}"
        + "}"
        + "@media (prefers-reduced-motion:reduce){"
        + f".d-kpi,{_panel()}{{transition:none;}}}}"
    )


def inject_styles() -> None:
    """Publish the design tokens and the stylesheet. Called once from app.py."""
    _markup("<style>" + _stylesheet() + "</style>")


# ---------------------------------------------------------------------------
# App chrome
# ---------------------------------------------------------------------------
def topbar(name: str, tagline: str, badge: str) -> None:
    """The portfolio heading: project title centred, provenance badge top-right.

    The badge is absolutely positioned rather than a flex sibling. As a sibling
    it would sit in the row and push the title off the true centre of the
    header by half its own width, which is exactly what "centred" has to mean
    here - the two blocks are unequal, so only taking one of them out of flow
    centres the other honestly.
    """
    _markup(
        '<div class="d-topbar">'
        '<div class="d-hero"><div class="d-hero-row">'
        '<span class="d-brand-mark"></span>'
        f'<h1 class="d-hero-title">{esc(name)}</h1>'
        "</div>"
        f'<div class="d-hero-sub">{esc(tagline)}</div>'
        "</div>"
        f'<span class="d-badge"><i></i>{esc(badge)}</span>'
        "</div>"
    )


def page_header(title: str, subtitle: str, meta: Sequence[str] = ()) -> None:
    """Page title, one-line explanation, and optional context chips.

    The heading is an ``h2`` because the document's ``h1`` is the project title
    in the header; two ``h1``s per page would leave a screen reader with no way
    to tell the site name from the current section.
    """
    chips = "".join(
        f'<span class="d-chip is-neutral">{esc(m)}</span>' for m in meta
    )
    _markup(
        '<div class="d-page-head"><div>'
        f'<h2 class="d-page-title">{esc(title)}</h2>'
        f'<div class="d-page-sub">{esc(subtitle)}</div>'
        "</div>"
        + (f'<div class="d-page-meta">{chips}</div>' if chips else "")
        + "</div>"
    )


def section(title: str, subtitle: str | None = None, *, small: bool = False) -> None:
    """A page-level section heading with an accent tick and optional subtitle."""
    cls = "d-section d-section-sm" if small else "d-section"
    _markup(f'<div class="{cls}"><span class="d-section-t">{esc(title)}</span></div>')
    if subtitle:
        _markup(f'<div class="d-section-s">{esc(subtitle)}</div>')


def spacer(height: int = 10) -> None:
    """A deliberate gap. Preferred to empty columns, which collapse in a grid."""
    _markup(f'<div style="height:{int(height)}px"></div>')


# ---------------------------------------------------------------------------
# Filter presentation
# ---------------------------------------------------------------------------
def reset_filter_widgets() -> None:
    """Clear every filter widget. Used as the Reset button's callback.

    Popping the key lets Streamlit fall back to the widget's own default, which
    is the full dataset. Assigning a value instead raises "cannot be modified
    after the widget with key ... is instantiated", because a callback runs
    before the next script pass, when the session is clear.
    """
    for key in FILTER_WIDGET_KEYS:
        st.session_state.pop(key, None)


def filter_bar(filters: Filters) -> None:
    """The always-visible strip: what is being shown, and how to clear it.

    This is the answer to "which data am I looking at right now" - it repeats
    the selection above the content on every page, so the sidebar is not the
    only place the current scope is defined. The reset action sits alongside it
    rather than only in the sidebar, because clearing a filter is something a
    reader does *after* reading the strip.
    """
    chips = filters.describe()
    if chips:
        body = "".join(
            '<span class="d-chip"><span class="d-chip-dot"></span>'
            f"{esc(chip)}</span>"
            for chip in chips
        )
    else:
        body = (
            '<span class="d-chip is-neutral">Every order, city, category, status '
            "and payment method</span>"
        )
    date_chip = (
        f'<span class="d-chip">{esc(filters.date_from.isoformat())}'
        f" &rarr; {esc(filters.date_to.isoformat())}</span>"
    )
    count = filters.active_count
    count_text = (
        f"{count} filter{'s' if count != 1 else ''} applied" if count else "Full dataset"
    )
    bar, action = st.columns([4.7, 1.0], gap="small", vertical_alignment="center")
    with bar:
        _markup(
            '<div class="d-filterbar">'
            '<span class="d-filterbar-label">Showing</span>'
            f"{date_chip}{body}"
            '<span class="d-filterbar-end">'
            f'<span class="d-filterbar-count">{esc(count_text)}</span>'
            "</span></div>"
        )
    with action:
        st.button(
            "Reset filters",
            key="main_reset",
            on_click=reset_filter_widgets,
            disabled=not count,
            width="stretch",
        )


# ---------------------------------------------------------------------------
# KPI and finding cards
# ---------------------------------------------------------------------------
@dataclass
class Kpi:
    """One metric tile.

    ``label`` and ``value`` are escaped before they reach the page, so a value
    that came from the database cannot inject markup. ``hint`` is inserted as
    trusted HTML because the supporting line legitimately carries a trend
    marker built by :func:`trend_hint`; every hint in the application is
    assembled by our own formatters.
    """

    label: str
    value: str
    hint: str | None = None
    accent: str = PALETTE["revenue"]
    small_value: bool = False


def _kpi_columns(count: int) -> int:
    """Pick a track count that fills whole rows at this card count.

    A band of eight at five columns leaves three empty-looking cards on the
    second row; at four it is a clean 4x2 block. Preference order is widest
    first, so five stays a single row while eight and ten both tile exactly.
    """
    if count <= 5:
        return count
    for cols in (4, 3, 5):
        if count % cols == 0:
            return cols
    return 4


def kpi_grid(cards: Sequence[Kpi], columns: int = 0) -> None:
    """Render metric tiles as one CSS grid.

    The band width is published as ``--d-kpi-cols`` rather than baked into the
    stylesheet, so a band of five is a single clean row on a wide screen instead
    of three tiles and a gap. The stylesheet's media queries step that number
    down with the content width, so the same markup stays usable on a laptop
    without a second column count to maintain.
    """
    if not cards:
        return
    if columns <= 0:
        columns = _kpi_columns(len(cards))
    columns = max(1, min(int(columns), len(cards)))
    parts = [f'<div class="d-kpi-grid" style="--d-kpi-cols:{columns}">']
    for card in cards:
        value_cls = "d-kpi-value sm" if (card.small_value or len(card.value) > 14) else "d-kpi-value"
        hint = f'<div class="d-kpi-hint">{card.hint}</div>' if card.hint else ""
        parts.append(
            f'<div class="d-kpi" style="--kpi:{esc(card.accent)}">'
            f'<div class="d-kpi-label">{esc(card.label)}</div>'
            f'<div class="{value_cls}">{esc(card.value)}</div>'
            f"{hint}</div>"
        )
    parts.append("</div>")
    _markup("".join(parts))


def trend_hint(current: float | None, previous: float | None, suffix: str = "") -> str:
    """Small green/red change string for a KPI card hint."""
    if current is None or previous in (None, 0):
        return ""
    change = 100 * (current - previous) / abs(previous)
    if abs(change) < 0.05:
        return f"unchanged {esc(suffix)}".strip()
    arrow = "&#9650;" if change > 0 else "&#9660;"
    klass = "up" if change > 0 else "down"
    return f'<span class="{klass}">{arrow} {abs(change):.1f}%</span> {esc(suffix)}'.strip()


def finding(label: str, headline: str, detail: str, accent: str = PALETTE["revenue"]) -> None:
    """A single stated finding: what it is, the number, and the sentence around it.

    ``headline`` and ``detail`` are escaped, so a product or customer name read
    from the database cannot inject markup into the Insights page.
    """
    _markup(
        f'<div class="d-find" style="--kpi:{esc(accent)}">'
        f'<div class="d-find-label">{esc(label)}</div>'
        f'<div class="d-find-value">{esc(headline)}</div>'
        f'<div class="d-find-text">{esc(detail)}</div>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def panel(title: str | None = None, subtitle: str | None = None) -> Iterator[None]:
    """A bordered card for a chart, table or short block of content.

    ``st.container(border=True)`` gives a real, keyboard-navigable container, so
    the visual card is the native one with its border, radius and shadow
    restyled - not a decorative wrapper that could hide a control.
    """
    with st.container(border=True):
        if title:
            section(title, subtitle, small=True)
        yield


def chart(figure: Any, key: str, *, height: int | None = None) -> None:
    """Render a Plotly figure with the shared toolbar and no theme override.

    ``theme=None`` stops Streamlit from repainting the figure with its own
    default template, so the figures keep the palette defined in
    :mod:`dashboard.charts`. The height is only sent when one is given:
    Streamlit rejects ``height=None``, and letting the figure's own layout
    height stand is the default behaviour anyway.
    """
    extra: dict[str, Any] = {}
    if height is not None:
        extra["height"] = int(height)
    st.plotly_chart(
        figure,
        width="stretch",
        theme=None,
        config=CHART_CONFIG,
        key=key,
        **extra,
    )


def bar_height(rows: int, *, minimum: int = CHART_SIZE["sm"], row: int = BAR_ROW_MIN) -> int:
    """Height for a horizontal bar chart so N labels never overlap."""
    return max(minimum, int(rows) * row + 78)


# ---------------------------------------------------------------------------
# Callouts, bullets, states
# ---------------------------------------------------------------------------
def definition_note(text: str, tag: str = "Definition") -> None:
    """A quiet definition/caution strip - the UI equivalent of a SQL comment."""
    _markup(
        f'<div class="d-note"><span class="d-note-tag">{esc(tag)}</span>'
        f"<span>{text}</span></div>"
    )


def callout(text: str, *, tone: str = "info", tag: str = "Note") -> None:
    """A tinted note strip. ``tone`` is ``info``, ``warn`` or ``neutral``."""
    cls = {"info": "d-note info", "warn": "d-note warn", "neutral": "d-note"}.get(tone, "d-note")
    _markup(
        f'<div class="{cls}"><span class="d-note-tag">{esc(tag)}</span>'
        f"<span>{text}</span></div>"
    )


def bullets(items: Sequence[str]) -> None:
    """A bulleted list inside one card, for caveats and method notes."""
    body = "".join(f"<li>{item}</li>" for item in items)
    _markup(f'<div class="d-bullets"><ul>{body}</ul></div>')


def data_table(
    frame: pd.DataFrame,
    column_config: dict[str, Any] | None = None,
    *,
    height: int | None = None,
    key: str | None = None,
    empty_message: str = "No data for the selected filters.",
) -> None:
    """``st.dataframe`` wrapper with consistent defaults and an empty state."""
    if frame is None or len(frame) == 0:
        empty_state(empty_message)
        return
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        height=height,
        column_config=column_config or {},
        key=key,
    )


def empty_state(
    message: str = "No data found for the selected filters.",
    hint: str | None = None,
) -> None:
    """The one 'nothing to show' block used everywhere."""
    st.info(message)
    if hint:
        st.caption(hint)


def caption(text: str) -> None:
    st.caption(text)


def error_panel(message: str, *, hint: str | None = None) -> None:
    """A friendly failure block.

    Deliberately has no parameter for a traceback, a SQL statement or an
    exception string, so there is no way for one to reach the page. A
    diagnostic the reader cannot act on is noise in the middle of a business
    dashboard, and the full traceback is written to ``dashboard/dashboard.log``
    by the caller instead.

    Not showing the traceback is not hiding the failure: ``message`` is always
    shown, always names what went wrong, and ``hint`` always says where the
    detail went.
    """
    st.error(message)
    if hint:
        st.caption(hint)


def connection_badge(ok: bool, message: str, container: Any = None) -> None:
    """Database availability line, shown before any query runs.

    The status belongs next to the filters that depend on it, so it goes in the
    sidebar by default. ``container`` is a parameter rather than a hard-coded
    ``st.sidebar`` call only so the component stays reusable.
    """
    cls = "d-conn is-ok" if ok else "d-conn is-bad"
    _markup(f'<div class="{cls}"><i></i>{esc(message)}</div>',
            container if container is not None else st.sidebar)


def loading(text: str):
    return st.spinner(text)
