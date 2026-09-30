"""Plotly chart builders - the dashboard's chart theme.

Every figure in the application is produced here so they share one visual
language: the same fonts, the same hairline grid, the same colour meanings
(violet = revenue, cyan = profit, emerald = success, amber = pending, rose =
failure, pink = returns) and the same hover format.

Two deliberate conventions:

* **Titles live in the card header, not in the figure.** ``components.panel``
  renders the heading above the plot, so the plot gets the full card height and
  the two never drift apart.
* **One unit per axis.** Money axes abbreviate (500M), count axes use thousands
  separators, percentage axes are already 0-100 so they only need a ``%``
  suffix. No chart invents its own formatting.

DARK SURFACE
------------
``paper_bgcolor`` and ``plot_bgcolor`` are both fully transparent. That is what
lets a plot sit inside a CSS card and inherit the card's fill, so a chart can
never end up as a lighter rectangle pasted onto a dark card - the most common
way a themed dashboard falls apart. Nothing here paints a background of its
own; the only opaque surface Plotly draws is the hover label.

No chart hardcodes a data value; they all receive a DataFrame.
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import (
    CATEGORICAL,
    CHART_SIZE,
    FONT_STACK,
    PALETTE,
    SURFACE,
)

# ---------------------------------------------------------------------------
# Shared theme
# ---------------------------------------------------------------------------
TEXT = SURFACE["text"]
TEXT_SOFT = SURFACE["text_soft"]
TEXT_MUTED = SURFACE["text_muted"]
GRID = SURFACE["grid"]
BORDER = SURFACE["border"]
CARD = SURFACE["card"]
CANVAS = SURFACE["canvas"]

BASE_LAYOUT = dict(
    font=dict(family=FONT_STACK, size=12.5, color=TEXT_SOFT),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=4, r=10, t=8, b=4),
    hovermode="closest",
    hoverlabel=dict(
        bgcolor=SURFACE["inset"],
        font=dict(size=12, color=TEXT, family=FONT_STACK),
        bordercolor=BORDER,
        align="left",
    ),
    legend=dict(
        orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
        font=dict(size=11.5, color=TEXT_SOFT),
        bgcolor="rgba(0,0,0,0)", borderwidth=0, itemwidth=30,
    ),
    colorway=CATEGORICAL,
    separators=",.",
    showlegend=True,
)

# Horizontal bars share a value-axis format: abbreviated money.
MONEY_AXIS = "~s"
COUNT_AXIS = ",d"

# Status hues are referenced by name in several charts, so the semantic mapping
# lives in one place. Order status and payment status share names, so one map
# covers both - the label is the same word with a different subject.
STATUS_HUE = {
    "Completed": PALETTE["success"],
    "Pending": PALETTE["warning"],
    "Cancelled": PALETTE["danger"],
    "Returned": PALETTE["returned"],
    "Paid": PALETTE["success"],
    "Failed": PALETTE["danger"],
    "Refunded": PALETTE["returned"],
}


def status_hue(name: Any) -> str:
    """Colour for a status label, falling back to the neutral slate."""
    return STATUS_HUE.get(str(name), PALETTE["neutral"])


def _apply(
    fig: go.Figure,
    *,
    height: int = CHART_SIZE["md"],
    legend: bool = True,
    legend_top: bool = True,
    grid: str = "",
    grid_format: str = MONEY_AXIS,
    percent: str = "",
) -> go.Figure:
    """Apply the shared theme and neutralise the per-chart axis chrome.

    ``grid`` names the axis that carries the hairline gridlines ("x" for a
    horizontal bar chart, "y" for a vertical one) and ``grid_format`` its tick
    format. ``percent`` names the axis whose values are already 0-100, so the
    suffix is added without rescaling anything.

    Both are parameters rather than follow-up calls on purpose. The theme turns
    gridlines *off* on both axes, so a builder that called a ``_grid_x()`` helper
    and then applied the theme lost the gridlines every time - and did so
    silently, because the figure still rendered. Making the choice part of the
    one call that owns the axis chrome removes the ordering trap.
    """
    layout = dict(BASE_LAYOUT)
    if not legend:
        layout["showlegend"] = False
    fig.update_layout(**layout, height=height)
    if not legend_top:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.22,
                                      xanchor="left", x=0, font=dict(size=11.5,
                                                                    color=TEXT_SOFT)))
    common = dict(
        zeroline=False,
        linecolor="rgba(0,0,0,0)",
        tickfont=dict(size=11.5, color=TEXT_MUTED),
        ticks="",
        automargin=True,
    )
    for axis, updater in (("x", fig.update_xaxes), ("y", fig.update_yaxes)):
        settings = dict(common)
        settings["showgrid"] = axis == grid
        if axis == grid:
            settings.update(gridcolor=GRID, gridwidth=1, tickformat=grid_format)
        if axis == percent:
            settings["ticksuffix"] = "%"
        updater(**settings)
    return fig


def empty_figure(message: str = "No data for the selected filters") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=esc_plotly(message), showarrow=False,
        font=dict(size=13, color=TEXT_MUTED, family=FONT_STACK),
        xref="paper", yref="paper", x=0.5, y=0.5,
    )
    layout = dict(BASE_LAYOUT, showlegend=False, height=CHART_SIZE["sm"],
                  margin=dict(l=0, r=0, t=0, b=0))
    fig.update_layout(**layout, xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def esc_plotly(text: str) -> str:
    """Minimal escaping for the few strings passed into a Plotly annotation."""
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _guard(frame: pd.DataFrame, message: str = "No data for the selected filters"):
    return None if frame is not None and not frame.empty else empty_figure(message)


def _ink_on(colours: Sequence[str]) -> list[str]:
    """One label colour per slice, measured against the arc it sits on.

    A pie is the only chart here whose label rests *on* a data mark rather
    than beside it, and the palette deliberately spans both ends: white ink on
    the amber and emerald arcs lands near 1.9:1, near-black ink on the deep
    violet arcs lands near 1.2:1. No single colour survives both, so each
    label is resolved against its own fill instead of against the palette.

    The threshold is the luminance at which near-black overtakes white as the
    better contrast; every fill in ``PALETTE`` and ``CATEGORICAL`` sits well
    clear of it on one side or the other.
    """
    cutoff = 0.18
    ink = []
    for colour in colours:
        r, g, b = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
        channel = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                   for c in (r, g, b)]
        lum = 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2]
        ink.append(CANVAS if lum > cutoff else TEXT)
    return ink


def _shares(values: Sequence[float]) -> list[str]:
    """Each value as a share of the total, formatted here rather than by Plotly.

    Plotly's own ``%{percent}`` runs through d3-format under the *viewer's*
    locale, and on this stack that renders 75.6 as "75,6" - a comma where every
    other number in the dashboard uses a decimal point, including the money
    figures two cards away. Computing the string in Python gives the on-arc
    label, the tooltip and the KPI cards one number format, and takes the
    label off the browser's locale entirely.
    """
    total = sum(values)
    if total <= 0:
        return [f"{0.0:.1f}%" for _ in values]
    return [f"{value / total * 100:.1f}%" for value in values]


def _donut(
    labels: Sequence[str],
    values: Sequence[Any],
    colours: Sequence[str],
    centre_value: str,
    centre_label: str,
    hover: str,
) -> go.Figure:
    """A donut with the total in the middle - used wherever a mix is shown.

    The share of each slice is printed on the arc. A mix chart exists to make
    the split legible at a glance, and a legend of bare names leaves the reader
    to compare wedge angles by eye - which is the one thing a wedge is worst at.
    The value and the share both stay in the hover as well; ``hover`` reads the
    share from ``customdata`` so the tooltip and the arc cannot disagree.
    """
    fills = list(colours)
    shares = _shares([float(v or 0) for v in values])
    fig = go.Figure(go.Pie(
        labels=list(labels), values=list(values), hole=0.62,
        marker=dict(colors=fills, line=dict(color=CARD, width=2)),
        text=shares, textinfo="text", textposition="inside",
        insidetextorientation="horizontal",
        textfont=dict(size=12.5, color=_ink_on(fills), family=FONT_STACK),
        customdata=shares,
        sort=False, direction="clockwise",
        hovertemplate=hover,
    ))
    fig.add_annotation(
        text=f"<b>{centre_value}</b><br>"
             f"<span style='font-size:10.5px;color:{TEXT_MUTED}'>{centre_label}</span>",
        showarrow=False, font=dict(size=17, color=TEXT, family=FONT_STACK),
    )
    fig.update_layout(
        legend=dict(orientation="v", yanchor="middle", y=0.5, x=1.0,
                    font=dict(size=11.5, color=TEXT_SOFT), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=6, b=0),
        # A four-way mix leaves narrow slices, and Plotly's default is to drop
        # text that does not fit - which is exactly the share a reader most
        # wants. "show" keeps every percentage and lets the type shrink instead.
        uniformtext=dict(minsize=9.5, mode="show"),
    )
    return fig


def _wrap_label(text: Any, width: int = 24, max_lines: int = 2) -> str:
    """Break a long category name over at most ``max_lines`` short lines.

    Product names in this dataset run to forty characters ("Dawlance Single
    Door Refrigerator Paperback"). On a horizontal bar chart that text is the
    y axis, so Plotly's automargin gives the label column whatever it needs and
    squeezes the bars into what is left - which on a half-width card leaves
    almost nothing to read. Wrapping caps the label column at a predictable
    width; the full name stays in the hover tooltip, because the tick text is
    set separately from the data and ``%{y}`` still resolves to the real name.
    """
    words = str(text).split()
    if not words:
        return ""
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    if len(lines) > max_lines:
        kept = lines[:max_lines]
        kept[-1] = kept[-1][: max(1, width - 1)].rstrip() + "\u2026"
        lines = kept
    return "<br>".join(lines)


def _hbar(
    labels: Sequence[str],
    values: Sequence[Any],
    *,
    colour: str | Sequence[str],
    hover: str,
    money: bool = True,
    height: int | None = None,
    customdata: Any = None,
    wrap: int = 0,
) -> go.Figure:
    """Horizontal bar chart, largest at the top, with a hover template.

    Horizontal is the default for ranked lists because product and city names
    are long; a vertical bar chart turns them into unreadable rotated ticks.
    ``wrap`` is the character budget for each tick line, or 0 to leave the
    labels alone.
    """
    labels = list(labels)
    values = list(values)
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colour, line=dict(width=0)),
        customdata=customdata,
        hovertemplate=hover,
        cliponaxis=False,
    ))
    row = 30
    if wrap:
        tick_text = [_wrap_label(label, wrap) for label in labels]
        if any("<br>" in text for text in tick_text):
            # A two-line tick needs more room than a one-line one.
            row = 34
        fig.update_yaxes(tickmode="array", tickvals=labels, ticktext=tick_text)
    if height is None:
        height = max(CHART_SIZE["md"], len(labels) * row + 74)
    return _apply(fig, height=height, legend=False, grid="x",
                  grid_format=MONEY_AXIS if money else COUNT_AXIS)


# ---------------------------------------------------------------------------
# Revenue, profit and value
# ---------------------------------------------------------------------------
def revenue_profit_trend(frame: pd.DataFrame) -> go.Figure:
    """Realised revenue and profit by month, revenue shaded."""
    if (g := _guard(frame)) is not None:
        return g
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=frame["month"], y=frame["realised_revenue"], name="Realised revenue",
        mode="lines", line=dict(color=PALETTE["revenue"], width=2.4, shape="spline",
                                smoothing=0.35),
        fill="tozeroy", fillcolor="rgba(37,99,235,0.09)",
        hovertemplate="%{x}<br>Revenue <b>PKR %{y:,.0f}</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=frame["month"], y=frame["realised_profit"], name="Realised profit",
        mode="lines", line=dict(color=PALETTE["profit"], width=2.4, shape="spline",
                                smoothing=0.35),
        hovertemplate="%{x}<br>Profit <b>PKR %{y:,.0f}</b><extra></extra>",
    ))
    fig.update_layout(hovermode="x unified")
    return _apply(fig, height=CHART_SIZE["lg"], grid="y")


def order_volume_trend(frame: pd.DataFrame) -> go.Figure:
    """Monthly orders with the completed subset overlaid."""
    if (g := _guard(frame)) is not None:
        return g
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=frame["month"], y=frame["orders"], name="All orders",
        marker=dict(color=PALETTE["revenue_soft"], line=dict(width=0)),
        hovertemplate="%{x}<br>Orders <b>%{y:,.0f}</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=frame["month"], y=frame["completed_orders"], name="Completed",
        mode="lines", line=dict(color=PALETTE["success"], width=2.2,
                                shape="spline", smoothing=0.35),
        hovertemplate="%{x}<br>Completed <b>%{y:,.0f}</b><extra></extra>",
    ))
    return _apply(fig, height=CHART_SIZE["lg"], grid="y", grid_format=COUNT_AXIS)


def aov_trend(frame: pd.DataFrame) -> go.Figure:
    """Average order value per month = realised revenue / completed orders."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.copy()
    data["aov"] = [
        (r["realised_revenue"] / r["completed_orders"]) if r["completed_orders"] else None
        for _, r in data.iterrows()
    ]
    fig = go.Figure(go.Scatter(
        x=data["month"], y=data["aov"], mode="lines+markers", name="AOV",
        line=dict(color=PALETTE["revenue"], width=2.4, shape="spline", smoothing=0.35),
        marker=dict(size=5, color=CARD, line=dict(color=PALETTE["revenue"], width=1.6)),
        fill="tozeroy", fillcolor="rgba(37,99,235,0.07)",
        hovertemplate="%{x}<br>AOV <b>PKR %{y:,.0f}</b><extra></extra>",
    ))
    return _apply(fig, height=CHART_SIZE["md"], legend=False, grid="y")


def value_bridge(realised: float, lost: float, pending: float) -> go.Figure:
    """Gross order value split into realised, lost and still-pending value.

    One stacked bar, so the three quantities can only be read as parts of the
    same whole - the point the whole dashboard keeps making about the
    difference between realised and potential value.
    """
    realised = float(realised or 0)
    lost = float(lost or 0)
    pending = float(pending or 0)
    total = realised + lost + pending
    if not total:
        return empty_figure("No value in the selected scope")
    segments = [
        ("Realised", PALETTE["success"], realised),
        ("Not completed", PALETTE["danger"], lost),
        ("Pending", PALETTE["warning"], pending),
    ]
    fig = go.Figure(go.Bar(
        x=[total], y=[""], orientation="h",
        marker=dict(color=[c for _, c, _ in segments], line=dict(color=CARD, width=1)),
        customdata=[[realised, lost, pending]],
        hovertemplate=(
            "Realised <b>PKR %{customdata[0]:,.0f}</b><br>"
            "Not completed <b>PKR %{customdata[1]:,.0f}</b><br>"
            "Pending <b>PKR %{customdata[2]:,.0f}</b><extra></extra>"
        ),
    ))
    # Label a segment only when it is wide enough to hold the word, and place
    # the label at the segment's left edge so it stays inside the bar.
    offset = 0.0
    for name, _colour, value in segments:
        if value / total >= 0.08:
            fig.add_annotation(
                x=offset, y=0, showarrow=False, text=f"<b>{name}</b>",
                font=dict(size=11.5, color=TEXT, family=FONT_STACK),
                xanchor="left", xshift=8,
            )
        offset += value
    fig.update_layout(barmode="stack", showlegend=False, bargap=0.6)
    return _apply(fig, height=124, legend=False)


def category_performance(frame: pd.DataFrame, top: int = 10) -> go.Figure:
    """Realised revenue and profit side by side, by category."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.head(top).iloc[::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=data["category"], x=data["realised_revenue"], name="Revenue",
        orientation="h", marker=dict(color=PALETTE["revenue"], line=dict(width=0)),
        hovertemplate="%{y}<br>Revenue <b>PKR %{x:,.0f}</b><extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=data["category"], x=data["realised_profit"], name="Profit",
        orientation="h", marker=dict(color=PALETTE["profit_soft"], line=dict(width=0)),
        hovertemplate="%{y}<br>Profit <b>PKR %{x:,.0f}</b><extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.34, bargroupgap=0.12)
    return _apply(fig, height=max(CHART_SIZE["lg"], len(data) * 34 + 66), grid="x")


def margin_by_category(frame: pd.DataFrame) -> go.Figure:
    """Realised profit margin by category, against a 30% reference line."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.copy()
    data["margin_pct"] = [
        (100 * r["realised_profit"] / r["realised_revenue"]) if r["realised_revenue"] else 0.0
        for _, r in data.iterrows()
    ]
    data = data.sort_values("margin_pct").tail(12)
    colours = [
        PALETTE["success"] if m >= 30 else PALETTE["profit"] if m >= 20
        else PALETTE["warning"]
        for m in data["margin_pct"]
    ]
    fig = go.Figure(go.Bar(
        x=data["margin_pct"], y=data["category"], orientation="h",
        marker=dict(color=colours, line=dict(width=0)),
        customdata=data[["realised_revenue"]].to_numpy(),
        hovertemplate="%{y}<br>Margin <b>%{x:.2f}%</b><br>"
                      "Revenue <b>PKR %{customdata[0]:,.0f}</b><extra></extra>",
    ))
    fig.add_vline(x=30, line=dict(color=TEXT_MUTED, width=1, dash="dash"))
    fig.add_annotation(x=30, y=1, yref="paper", yanchor="bottom", xanchor="left",
                       text=" 30% target", showarrow=False,
                       font=dict(size=10.5, color=TEXT_MUTED))
    return _apply(fig, height=max(CHART_SIZE["md"], len(data) * 30 + 74), legend=False,
                  grid="x", grid_format=",.0f", percent="x")


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------
def city_revenue(frame: pd.DataFrame, top: int = 12) -> go.Figure:
    """Realised revenue by shipping city, the leader highlighted."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.head(top).iloc[::-1]
    total = frame["realised_revenue"].sum() or 1
    colours = [PALETTE["revenue"] if i == len(data) - 1 else PALETTE["revenue_dim"]
               for i in range(len(data))]
    return _hbar(
        data["city"], data["realised_revenue"], colour=colours,
        hover="%{y}<br>Revenue <b>PKR %{x:,.0f}</b><br>"
              "Share of all cities <b>%{customdata:.1f}%</b><extra></extra>",
        customdata=(100 * data["realised_revenue"] / total).to_numpy(),
        height=max(CHART_SIZE["lg"], len(data) * 28 + 68),
    )


def orders_by_city_volume(frame: pd.DataFrame, top: int = 12) -> go.Figure:
    """Order counts by shipping city, largest first."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.head(top).iloc[::-1]
    total = frame["orders"].sum() or 1
    colours = [PALETTE["revenue"] if i == len(data) - 1 else PALETTE["revenue_dim"]
               for i in range(len(data))]
    return _hbar(
        data["city"], data["orders"], colour=colours, money=False,
        hover="%{y}<br>Orders <b>%{x:,.0f}</b><br>"
              "Share of all cities <b>%{customdata:.1f}%</b><extra></extra>",
        customdata=(100 * data["orders"] / total).to_numpy(),
        height=max(CHART_SIZE["lg"], len(data) * 28 + 68),
    )


def subcategory_revenue(frame: pd.DataFrame, top: int = 12) -> go.Figure:
    """Top subcategories, coloured by their parent category."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.head(top).iloc[::-1]
    return _hbar(
        data["subcategory"], data["realised_revenue"],
        colour=list(CATEGORICAL[: len(data)]),
        hover="%{customdata[0]}<br>%{y}<br>Revenue <b>PKR %{x:,.0f}</b><extra></extra>",
        customdata=data[["category"]].to_numpy(),
        height=max(CHART_SIZE["lg"], len(data) * 34 + 68), wrap=20,
    )


# ---------------------------------------------------------------------------
# Order status
# ---------------------------------------------------------------------------
def mix_donut(frame: pd.DataFrame, label_col: str, value_col: str,
              centre_label: str) -> go.Figure:
    """A donut for any mix that is named by a label column.

    Order status and payment status are different populations with overlapping
    names, so they are drawn with the same builder but never from the same
    frame.
    """
    if (g := _guard(frame)) is not None:
        return g
    fig = _donut(
        frame[label_col], frame[value_col],
        [status_hue(name) for name in frame[label_col]],
        f"{int(frame[value_col].sum()):,}", centre_label,
        "%{label}<br>Count <b>%{value:,.0f}</b><br>"
        "Share <b>%{customdata}</b><extra></extra>",
    )
    return _apply(fig, height=CHART_SIZE["md"])


def status_distribution(frame: pd.DataFrame) -> go.Figure:
    """Donut of the order-status mix in scope."""
    return mix_donut(frame, "status", "orders", "orders in scope")


def payment_status_distribution(frame: pd.DataFrame) -> go.Figure:
    """Donut of the payment-status mix in scope - a different population."""
    return mix_donut(frame, "payment_status", "payments", "payments in scope")


def status_value_split(frame: pd.DataFrame) -> go.Figure:
    """Value attached to each order status - potential value, not realised."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.iloc[::-1]
    total = frame["gross_order_value"].sum() or 1
    return _hbar(
        data["status"], data["gross_order_value"],
        colour=[status_hue(s) for s in data["status"]],
        hover="%{y}<br>Value <b>PKR %{x:,.0f}</b><br>"
              "Share of gross <b>%{customdata:.1f}%</b><extra></extra>",
        customdata=(100 * data["gross_order_value"] / total).to_numpy(),
        height=max(CHART_SIZE["md"], len(data) * 32 + 68),
    )


def order_mix_trend(frame: pd.DataFrame) -> go.Figure:
    """Monthly orders with the completion rate on a second axis."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.copy()
    data["rate"] = [
        (100.0 * r["completed_orders"] / r["orders"]) if r["orders"] else None
        for _, r in data.iterrows()
    ]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=data["month"], y=data["orders"], name="Orders",
        marker=dict(color=PALETTE["revenue_soft"], line=dict(width=0)),
        hovertemplate="%{x}<br>Orders <b>%{y:,.0f}</b><extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=data["month"], y=data["rate"], name="Completion rate",
        mode="lines", line=dict(color=PALETTE["success"], width=2.2, shape="spline",
                                smoothing=0.35),
        hovertemplate="%{x}<br>Completion rate <b>%{y:.2f}%</b><extra></extra>",
    ), secondary_y=True)
    fig.update_layout(hovermode="x unified")
    fig = _apply(fig, height=CHART_SIZE["lg"], grid="y", grid_format=COUNT_AXIS)
    # The completion rate rides a second axis. The shared theme reaches every
    # y-type axis, so the secondary one is corrected afterwards: a percent
    # format, and no gridlines of its own, otherwise two ruled scales compete
    # and neither reads as the secondary one.
    fig.update_yaxes(secondary_y=True, tickformat=".0f", ticksuffix="%", showgrid=False,
                     zeroline=False, linecolor="rgba(0,0,0,0)", ticks="",
                     tickfont=dict(size=11.5, color=PALETTE["success"]))
    return fig


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
def top_products(frame: pd.DataFrame, value_col: str, *, top: int = 10,
                 money: bool = True) -> go.Figure:
    """A ranked product list. Long product names read correctly on a y axis."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.head(top).iloc[::-1]
    total = frame[value_col].sum() or 1
    hover = (
        "%{customdata[0]}<br>%{y}<br>Revenue <b>PKR %{x:,.0f}</b><br>"
        "Share of catalogue <b>%{customdata[1]:.1f}%</b><extra></extra>"
        if money else
        "%{customdata[0]}<br>%{y}<br>Units <b>%{x:,.0f}</b><br>"
        "Share of catalogue <b>%{customdata[1]:.1f}%</b><extra></extra>"
    )
    customdata = [
        [row.get("category", ""), 100 * value / total]
        for (_, row), value in zip(data.iterrows(), data[value_col])
    ]
    return _hbar(
        data["product_name"], data[value_col],
        colour=PALETTE["revenue"] if money else PALETTE["profit"],
        hover=hover, customdata=customdata, money=money,
        height=max(CHART_SIZE["xl"], len(data) * 34 + 68), wrap=22,
    )


def product_bands(frame: pd.DataFrame) -> go.Figure:
    """Revenue per line and margin by discount band, on two axes."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.copy()
    data["margin_pct"] = [
        (100 * r["realised_profit"] / r["realised_revenue"]) if r["realised_revenue"] else 0.0
        for _, r in data.iterrows()
    ]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=data["discount_band"], y=data["revenue_per_line"], name="Revenue per line",
        marker=dict(color=PALETTE["revenue"], line=dict(width=0)),
        hovertemplate="%{x}<br>Revenue per line <b>PKR %{y:,.0f}</b><extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=data["discount_band"], y=data["margin_pct"], name="Margin",
        mode="lines+markers", line=dict(color=PALETTE["danger"], width=2.4),
        marker=dict(size=7, color=CARD, line=dict(color=PALETTE["danger"], width=1.8)),
        hovertemplate="%{x}<br>Margin <b>%{y:.2f}%</b><extra></extra>",
    ), secondary_y=True)
    fig.update_layout(hovermode="x unified")
    fig = _apply(fig, height=CHART_SIZE["xl"], grid="y")
    fig.update_yaxes(secondary_y=True, tickformat=".0f", ticksuffix="%", showgrid=False,
                     zeroline=False, linecolor="rgba(0,0,0,0)", ticks="",
                     tickfont=dict(size=11.5, color=PALETTE["danger"]))
    return fig


def units_per_line_by_band(frame: pd.DataFrame) -> go.Figure:
    """Units per line by discount band, against the undiscounted level."""
    if (g := _guard(frame)) is not None:
        return g
    fig = go.Figure(go.Bar(
        x=frame["discount_band"], y=frame["units_per_line"],
        marker=dict(color=PALETTE["profit"], line=dict(width=0)),
        hovertemplate="%{x}<br>Units per line <b>%{y:.2f}</b><extra></extra>",
    ))
    base = frame["units_per_line"].iloc[0]
    fig.add_hline(y=base, line=dict(color=TEXT_MUTED, width=1, dash="dash"))
    fig.add_annotation(x=0, y=base, yref="y", xref="paper", yanchor="bottom",
                       xanchor="left", text=" no-discount level", showarrow=False,
                       font=dict(size=10.5, color=TEXT_MUTED))
    return _apply(fig, height=CHART_SIZE["md"], legend=False, grid="y",
                  grid_format=",.2f")


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
def top_customers(frame: pd.DataFrame, top: int = 10) -> go.Figure:
    """Highest-spending customers, with order count in the tooltip."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.head(top).iloc[::-1]
    total = frame["realised_revenue"].sum() or 1
    customdata = [
        [row["customer_id"], row["city"], row["orders"], 100 * value / total]
        for (_, row), value in zip(data.iterrows(), data["realised_revenue"])
    ]
    return _hbar(
        data["name"], data["realised_revenue"], colour=PALETTE["revenue"],
        hover="%{customdata[0]} &middot; %{customdata[1]}<br>%{y}<br>"
              "Revenue <b>PKR %{x:,.0f}</b> &middot; Orders <b>%{customdata[2]:,.0f}</b><br>"
              "Share of spend <b>%{customdata[3]:.1f}%</b><extra></extra>",
        customdata=customdata,
        height=max(CHART_SIZE["xl"], len(data) * 30 + 68), wrap=24,
    )


def orders_per_customer(frame: pd.DataFrame) -> go.Figure:
    """How many orders each customer placed, with the long tail bucketed."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.copy()
    buckets = [
        (1, 1, "1"), (2, 2, "2"), (3, 3, "3"),
        (4, 5, "4-5"), (6, 10, "6-10"),
    ]
    labels, values = [], []
    for lo, hi, label in buckets:
        values.append(int(data.loc[(data["orders_placed"] >= lo)
                                    & (data["orders_placed"] <= hi), "customers"].sum()))
        labels.append(label)
    tail = int(data.loc[data["orders_placed"] > 10, "customers"].sum())
    if tail:
        labels.append("11+")
        values.append(tail)
    total = sum(values) or 1
    colours = [PALETTE["revenue"] if i == 0 else PALETTE["revenue_dim"]
               for i in range(len(values))]
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker=dict(color=colours, line=dict(width=0)),
        customdata=[100 * v / total for v in values],
        hovertemplate="%{x} orders<br>Customers <b>%{y:,.0f}</b><br>"
                      "Share <b>%{customdata:.1f}%</b><extra></extra>",
    ))
    return _apply(fig, height=CHART_SIZE["md"], legend=False, grid="y",
                  grid_format=COUNT_AXIS)


def segment_mix(frame: pd.DataFrame) -> go.Figure:
    """One-time versus repeat customers, by count and by revenue."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.copy()
    colours = {"One-time": PALETTE["revenue_dim"], "Repeat": PALETTE["revenue"]}
    fig = make_subplots(
        rows=1, cols=2, specs=[[{"type": "domain"}, {"type": "domain"}]],
        subplot_titles=("By customer count", "By realised revenue"),
        horizontal_spacing=0.08,
    )
    for col, column, label in ((1, "customers", "Customers"), (2, "revenue", "Revenue")):
        fills = [colours.get(s, PALETTE["neutral"]) for s in data["segment"]]
        shares = _shares([float(v or 0) for v in data[column]])
        fig.add_trace(go.Pie(
            labels=data["segment"], values=data[column], hole=0.66,
            marker=dict(colors=fills,
                        line=dict(color=CARD, width=2)),
            # Same convention as `_donut`: the share is on the arc, the value
            # and the share are both in the hover. These two donuts are small
            # and have no legend of their own, so the arc label is the only
            # place a reader can see the split.
            text=shares, textinfo="text", textposition="inside",
            insidetextorientation="horizontal",
            textfont=dict(size=12, color=_ink_on(fills), family=FONT_STACK),
            customdata=shares,
            sort=False, showlegend=False,
            hovertemplate="%{label}<br>" + label +
                          " <b>%{value:,.0f}</b><br>"
                          "Share <b>%{customdata}</b><extra></extra>",
        ), row=1, col=col)
    fig.update_annotations(font=dict(size=11.5, color=TEXT_MUTED, family=FONT_STACK))
    # One-time customers are a small wedge of a two-way split, so the label is
    # held rather than dropped when the ring is thin. See `_donut`.
    fig.update_layout(showlegend=False,
                      uniformtext=dict(minsize=9, mode="show"))
    return _apply(fig, height=CHART_SIZE["lg"], legend=False)


def customer_revenue_scatter(frame: pd.DataFrame) -> go.Figure:
    """One point per customer: order count against realised spend."""
    if (g := _guard(frame)) is not None:
        return g
    fig = go.Figure(go.Scattergl(
        x=frame["orders"], y=frame["realised_revenue"], mode="markers",
        marker=dict(size=6, color=PALETTE["revenue_soft"], opacity=0.5,
                    line=dict(width=0)),
        hovertemplate="Orders <b>%{x:,.0f}</b><br>Revenue <b>PKR %{y:,.0f}</b><extra></extra>",
    ))
    fig.update_xaxes(title_text="Orders placed", tickformat=COUNT_AXIS,
                     title_font=dict(size=11.5, color=TEXT_MUTED))
    fig.update_yaxes(title_text="Realised revenue (PKR)", tickformat=MONEY_AXIS,
                     title_font=dict(size=11.5, color=TEXT_MUTED))
    return _apply(fig, height=CHART_SIZE["xl"], legend=False, grid="y")


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------
def basket_size_trend(frame: pd.DataFrame) -> go.Figure:
    """Average units and lines per order, by month."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.copy()
    units = [
        (r["units"] / r["orders"]) if r["orders"] else None for _, r in data.iterrows()
    ]
    lines = [
        (r["line_count"] / r["orders"]) if r["orders"] else None for _, r in data.iterrows()
    ]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data["month"], y=units, name="Units per order", mode="lines",
        line=dict(color=PALETTE["revenue"], width=2.4, shape="spline", smoothing=0.35),
        hovertemplate="%{x}<br>Units per order <b>%{y:.2f}</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=data["month"], y=lines, name="Lines per order", mode="lines",
        line=dict(color=PALETTE["profit"], width=2.4, shape="spline", smoothing=0.35),
        hovertemplate="%{x}<br>Lines per order <b>%{y:.2f}</b><extra></extra>",
    ))
    fig.update_layout(hovermode="x unified")
    return _apply(fig, height=CHART_SIZE["lg"], grid="y", grid_format=",.2f")


def order_size_distribution(frame: pd.DataFrame) -> go.Figure:
    """How many orders fall into each basket-size band."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.copy()
    total = data["orders"].sum() or 1
    order = ["1 unit", "2 units", "3 units", "4-5 units", "6-8 units", "9+ units"]
    data["bucket"] = pd.Categorical(data["size_band"], categories=order, ordered=True)
    data = data.sort_values("bucket")
    colours = [PALETTE["revenue"] if i == 0 else PALETTE["revenue_dim"]
               for i in range(len(data))]
    return _hbar(
        data["bucket"].astype(str), data["orders"], colour=colours, money=False,
        hover="%{y}<br>Orders <b>%{x:,.0f}</b><br>"
              "Share of orders <b>%{customdata:.1f}%</b><extra></extra>",
        customdata=(100 * data["orders"] / total).to_numpy(),
        height=max(CHART_SIZE["md"], len(data) * 32 + 68),
    )


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
def payment_method_usage(frame: pd.DataFrame) -> go.Figure:
    """Payments per method, with each method's share of volume."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.sort_values("payments")
    total = frame["payments"].sum() or 1
    colours = [PALETTE["revenue"] if i == len(data) - 1 else PALETTE["revenue_dim"]
               for i in range(len(data))]
    return _hbar(
        data["payment_method"], data["payments"], colour=colours, money=False,
        hover="%{y}<br>Payments <b>%{x:,.0f}</b><br>"
              "Share of payments <b>%{customdata:.1f}%</b><extra></extra>",
        customdata=(100 * data["payments"] / total).to_numpy(),
        height=max(CHART_SIZE["md"], len(data) * 32 + 68),
    )


def payment_failure_rate(frame: pd.DataFrame) -> go.Figure:
    """Failure rate by method against the portfolio average."""
    if (g := _guard(frame)) is not None:
        return g
    data = frame.sort_values("failure_rate_pct")
    average = (100 * data["failed"].sum() / data["payments"].sum()) if data["payments"].sum() else 0
    colours = [PALETTE["danger"] if r >= average * 1.5 and r > 0 else PALETTE["warning"]
               for r in data["failure_rate_pct"]]
    fig = _hbar(
        data["payment_method"], data["failure_rate_pct"], colour=colours, money=False,
        hover="%{y}<br>Failed <b>%{customdata[0]:,.0f}</b> of "
              "<b>%{customdata[1]:,.0f}</b><br>Failure rate <b>%{x:.2f}%</b><extra></extra>",
        customdata=data[["failed", "payments"]].to_numpy(),
        height=max(CHART_SIZE["md"], len(data) * 32 + 68),
    )
    fig.update_xaxes(tickformat=",.2f", ticksuffix="%")
    fig.add_vline(x=average, line=dict(color=TEXT_MUTED, width=1, dash="dash"))
    fig.add_annotation(x=average, y=1, yref="paper", yanchor="bottom", xanchor="left",
                       text=f" portfolio {average:.2f}%", showarrow=False,
                       font=dict(size=10.5, color=TEXT_MUTED))
    return fig


def payment_status_heatmap(frame: pd.DataFrame) -> go.Figure:
    """Method-by-status payment counts, labelled with the actual counts."""
    if (g := _guard(frame)) is not None:
        return g
    pivot = frame.pivot_table(index="payment_method", columns="payment_status",
                              values="payments", aggfunc="sum", fill_value=0)
    totals = pivot.to_numpy()
    text = [[f"{int(v):,}" for v in row] for row in totals]
    fig = go.Figure(go.Heatmap(
        z=totals, x=list(pivot.columns), y=list(pivot.index),
        colorscale=[[0, "#1B1840"], [0.5, "#4C3FBF"], [1, "#9F8FFF"]],
        hovertemplate="%{y}<br>%{x}: <b>%{z:,.0f}</b> payments<extra></extra>",
        xgap=3, ygap=3,
        text=text, texttemplate="%{text}",
        textfont=dict(size=11.5, family=FONT_STACK, color=TEXT),
    ))
    fig.update_xaxes(side="top", showgrid=False,
                     tickfont=dict(size=11.5, color=TEXT_MUTED))
    fig.update_yaxes(showgrid=False, autorange="reversed",
                     tickfont=dict(size=11.5, color=TEXT_SOFT))
    return _apply(fig, height=max(CHART_SIZE["md"], len(pivot) * 34 + 92), legend=False)
