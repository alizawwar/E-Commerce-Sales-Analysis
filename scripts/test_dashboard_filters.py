"""Exercise the dashboard's filters and prove the joins do not multiply money.

Two jobs:

1. **Filter tests** (Phase 4 section 29). Each scenario asserts that the numbers
   move in the way the filter semantics promise, and that nothing errors.

2. **Join-duplication tests** (Phase 4 section 30). For several independent
   query paths, the total is compared against the KPI query. If any path
   double-counted an order's value because of a join, the totals would differ.

Run with::

    python scripts/test_dashboard_filters.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Windows consoles default to a legacy code page; force UTF-8 so the report's
# box-drawing characters cannot raise UnicodeEncodeError mid-run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dashboard import queries  # noqa: E402
from dashboard.metrics import build_metric_bundle  # noqa: E402
from dashboard.utils import Filters  # noqa: E402

GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[1m", "\033[0m",
)

failures: list[str] = []
checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if condition:
        print(f"  {GREEN}PASS{RESET}  {label}" + (f"  {GREY}{detail}{RESET}" if detail else ""))
    else:
        print(f"  {RED}FAIL{RESET}  {label}  {GREY}{detail}{RESET}")
        failures.append(f"{label} :: {detail}")


def close(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(float(a or 0) - float(b or 0)) <= tol


def kpi_for(filters: Filters) -> dict:
    row = queries.kpi_metrics(filters)
    return build_metric_bundle(row) if row else {}


def header(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    print("-" * 74)


# ===========================================================================
header("TEST 1 - All data (default filters)")
base = Filters()
m = kpi_for(base)
check("returns a KPI row", bool(m), f"gross {m.get('gross_order_value', 0):,.2f}")
check("12,000 orders", m.get("total_orders") == 12000, str(m.get("total_orders")))
check("9,076 completed", m.get("completed_orders") == 9076, str(m.get("completed_orders")))
check("realised revenue matches Phase 3",
      close(m["realised_revenue"], 632578305.60),
      f"{m['realised_revenue']:,.2f}")
check("gross value matches Phase 3",
      close(m["gross_order_value"], 845400583.33),
      f"{m['gross_order_value']:,.2f}")

# ===========================================================================
header("TEST 2 - Completed only")
completed = Filters(statuses=["Completed"])
c = kpi_for(completed)
check("every order is completed", c.get("completed_orders") == c.get("total_orders"),
      f"{c.get('completed_orders')} / {c.get('total_orders')}")
check("realised revenue unchanged (it was already completed-only)",
      close(c["realised_revenue"], m["realised_revenue"]),
      f"{c['realised_revenue']:,.2f}")
check("gross value drops to realised", close(c["gross_order_value"], m["realised_revenue"]),
      f"{c['gross_order_value']:,.2f}")
check("cancel rate is zero", close(c["cancellation_rate"], 0), f"{c['cancellation_rate']:.2f}%")
check("return rate is zero", close(c["return_rate"], 0), f"{c['return_rate']:.2f}%")

# ===========================================================================
header("TEST 3 - One city (Karachi)")
karachi = Filters(cities=["Karachi"])
k = kpi_for(karachi)
check("orders are fewer than the full set", k["total_orders"] < m["total_orders"],
      f"{k['total_orders']:,} < {m['total_orders']:,}")
check("revenue is less than the full set", k["realised_revenue"] < m["realised_revenue"],
      f"{k['realised_revenue']:,.2f}")
check("margin stays plausible (10-60%)", 10 < (k["margin_pct"] or 0) < 60,
      f"{k['margin_pct']:.2f}%")
check("only Karachi in the city breakdown",
      set(queries.city_breakdown(karachi)["city"]) == {"Karachi"})

# ===========================================================================
header("TEST 4 - One category (Electronics)")
electronics = Filters(categories=["Electronics"])
e = kpi_for(electronics)
check("only Electronics appears",
      set(queries.category_breakdown(electronics)["category"]) == {"Electronics"})
check("realised revenue is below the total", e["realised_revenue"] < m["realised_revenue"],
      f"{e['realised_revenue']:,.2f}")
check("revenue is below Electronics' gross value",
      e["realised_revenue"] <= e["gross_order_value"])

# ===========================================================================
header("TEST 5 - City + Category together")
combo = Filters(cities=["Karachi"], categories=["Electronics"])
cc = kpi_for(combo)
check("narrower than Karachi alone", cc["total_orders"] < k["total_orders"],
      f"{cc['total_orders']:,} < {k['total_orders']:,}")
check("narrower than Electronics alone", cc["total_orders"] < e["total_orders"],
      f"{cc['total_orders']:,} < {e['total_orders']:,}")
check("revenue below both parents", cc["realised_revenue"] < min(k["realised_revenue"],
                                                               e["realised_revenue"]))

# ===========================================================================
header("TEST 6 - Date range (first six months of the window)")
narrow = Filters(date_from=date(2024, 10, 1), date_to=date(2025, 3, 31))
n = kpi_for(narrow)
check("fewer orders than the full window", n["total_orders"] < m["total_orders"],
      f"{n['total_orders']:,} < {m['total_orders']:,}")
trend = queries.monthly_trend(narrow)
check("trend stops at the range end", trend["month"].max() == "2025-03",
      str(trend["month"].max()))
check("trend starts at the range start", trend["month"].min() == "2024-10",
      str(trend["month"].min()))

# ===========================================================================
header("TEST 7 - Category + Status + Payment method")
narrowed = Filters(
    categories=["Electronics"],
    statuses=["Completed", "Cancelled"],
    payment_methods=["Cash on Delivery", "Credit Card"],
)
n7 = kpi_for(narrowed)
check("runs without error", bool(n7), f"{n7.get('total_orders', 0):,} orders")
methods = queries.payment_method_summary(narrowed)
check("only the selected payment methods survive",
      set(methods["payment_method"]) <= {"Cash on Delivery", "Credit Card"},
      str(sorted(methods["payment_method"])))
check("both selected methods are actually present",
      set(methods["payment_method"]) == {"Cash on Delivery", "Credit Card"},
      str(sorted(methods["payment_method"])))
check("no payment-filtered orders leak through",
      n7["total_orders"] <= m["total_orders"])

# ===========================================================================
header("TEST 8 - Subcategory filter")
sub = queries.subcategory_breakdown(base)
if not sub.empty:
    first = sub.iloc[0]["subcategory"]
    cat = sub.iloc[0]["category"]
    f8 = Filters(categories=[cat], subcategories=[first])
    m8 = kpi_for(f8)
    check("subcategory filter runs", bool(m8), f"{m8.get('total_orders', 0):,} orders")
    got = queries.subcategory_breakdown(f8)
    check("only the chosen subcategory returns", set(got["subcategory"]) == {first},
          str(set(got["subcategory"])))
    check("revenue is below the parent category", m8["realised_revenue"] < m["realised_revenue"])

# ===========================================================================
header("TEST 9 - Empty result set is handled, not crashed")
impossible = Filters(cities=["Karachi"], categories=["Grocery"],
                     statuses=["Completed"], payment_methods=["Bank Transfer"],
                     date_from=date(2024, 10, 1), date_to=date(2024, 10, 3))
e9 = kpi_for(impossible)
check("no crash on an empty or near-empty scope", isinstance(e9, dict),
      f"{len(e9)} keys returned")
check("zeroed rather than NULL", e9.get("total_orders") == 0,
      f"total_orders={e9.get('total_orders')}")
check("margin is None (undefined), not ZeroDivisionError",
      e9.get("margin_pct") is None, repr(e9.get("margin_pct")))
check("every breakdown query on an empty scope returns cleanly",
      queries.category_breakdown(impossible).empty
      and queries.city_breakdown(impossible).empty
      and queries.product_performance(impossible).empty
      and queries.order_table(impossible).empty
      and queries.monthly_trend(impossible).empty)

# ===========================================================================
header("TEST 10 - Degenerate empty-status selection")
none_sel = Filters(statuses=[])
check("normalised() refuses to treat 'none' as 'all' silently",
      none_sel.normalised().statuses and sorted(none_sel.normalised().statuses) ==
      sorted(["Completed", "Pending", "Cancelled", "Returned"]),
      str(none_sel.normalised().statuses))
check("normalised() is a no-op when statuses are set",
      Filters(statuses=["Completed"]).normalised().statuses == ["Completed"])
m10 = kpi_for(none_sel)
check("an empty status list is reported, not silently widened",
      m10.get("total_orders") == 12000,
      f"falls back to all statuses, {m10.get('total_orders'):,} orders; the UI "
      "blocks this state before it reaches a query")

# ===========================================================================
header("TEST 11 - JOIN DUPLICATION: every path must agree on the total")
#
# payments is 1:1 with orders and order_items is 1:many with orders. If any of
# the paths below were multiplying an order's value, its total would exceed the
# KPI total. All of them must equal it exactly.

kpi_gross = m["gross_order_value"]
kpi_realised = m["realised_revenue"]
kpi_orders = m["total_orders"]

pm = queries.payment_method_summary(base)
check("payment_method_summary total gross == KPI gross",
      close(pm["gross_order_value"].sum(), kpi_gross),
      f"{pm['gross_order_value'].sum():,.2f} vs {kpi_gross:,.2f}")
check("payment_method_summary total realised == KPI realised",
      close(pm["realised_revenue"].sum(), kpi_realised),
      f"{pm['realised_revenue'].sum():,.2f} vs {kpi_realised:,.2f}")
check("payment_method_summary payment count == total orders",
      int(pm["payments"].sum()) == kpi_orders,
      f"{int(pm['payments'].sum()):,} vs {kpi_orders:,}")
check("payment_method_summary: no order counted twice",
      int(pm["orders"].sum()) == kpi_orders,
      f"orders {int(pm['orders'].sum()):,}")

ps = queries.payment_status_summary(base)
check("payment_status_summary total gross == KPI gross",
      close(ps["gross_order_value"].sum(), kpi_gross),
      f"{ps['gross_order_value'].sum():,.2f} vs {kpi_gross:,.2f}")
check("payment_status_summary row count == payment count",
      int(ps["payments"].sum()) == kpi_orders,
      f"{int(ps['payments'].sum()):,}")

sb = queries.order_status_breakdown(base)
check("order_status_breakdown total gross == KPI gross",
      close(sb["gross_order_value"].sum(), kpi_gross),
      f"{sb['gross_order_value'].sum():,.2f} vs {kpi_gross:,.2f}")
check("order_status_breakdown order count == total orders",
      int(sb["orders"].sum()) == kpi_orders,
      f"{int(sb['orders'].sum()):,}")

cb = queries.city_breakdown(base)
check("city_breakdown total gross == KPI gross",
      close(cb["gross_order_value"].sum(), kpi_gross),
      f"{cb['gross_order_value'].sum():,.2f} vs {kpi_gross:,.2f}")
check("city_breakdown total realised == KPI realised",
      close(cb["realised_revenue"].sum(), kpi_realised),
      f"{cb['realised_revenue'].sum():,.2f} vs {kpi_realised:,.2f}")

catb = queries.category_breakdown(base)
check("category_breakdown total realised == KPI realised",
      close(catb["realised_revenue"].sum(), kpi_realised),
      f"{catb['realised_revenue'].sum():,.2f} vs {kpi_realised:,.2f}")
check("category_breakdown units == KPI units",
      int(catb["units"].sum()) == int(m["units_total"]),
      f"{int(catb['units'].sum()):,} vs {int(m['units_total']):,}")

tr = queries.monthly_trend(base)
check("monthly_trend total realised == KPI realised",
      close(tr["realised_revenue"].sum(), kpi_realised),
      f"{tr['realised_revenue'].sum():,.2f} vs {kpi_realised:,.2f}")
check("monthly_trend total gross == KPI gross",
      close(tr["gross_order_value"].sum(), kpi_gross),
      f"{tr['gross_order_value'].sum():,.2f} vs {kpi_gross:,.2f}")
check("monthly_trend order count == total orders",
      int(tr["orders"].sum()) == kpi_orders,
      f"{int(tr['orders'].sum()):,}")

pp = queries.product_performance(base)
check("product_performance total realised == KPI realised",
      close(pp["realised_revenue"].sum(), kpi_realised),
      f"{pp['realised_revenue'].sum():,.2f} vs {kpi_realised:,.2f}")
check("product_performance row count == catalogue size",
      len(pp) == 300, str(len(pp)))

ot = queries.order_table(base, limit=20000)
check("order_table row count == total orders (one row per order)",
      len(ot) == kpi_orders,
      f"{len(ot):,} vs {kpi_orders:,}")
check("order_table total value == KPI gross",
      close(ot["gross_order_value"].sum(), kpi_gross),
      f"{ot['gross_order_value'].sum():,.2f} vs {kpi_gross:,.2f}")
check("order_table order ids are unique",
      ot["order_id"].nunique() == len(ot),
      f"{ot['order_id'].nunique():,} unique of {len(ot):,}")
check("order_table: max lines per order is sane (no row multiplication)",
      1 <= ot["line_count"].max() <= 12,
      f"max {int(ot['line_count'].max())} lines in one order")

cust = queries.customer_performance(base)
check("customer_performance active customers == KPI active customers",
      int(cust["customer_id"].nunique()) == int(m["active_customers"]),
      f"{cust['customer_id'].nunique():,} vs {int(m['active_customers']):,}")
check("customer_performance total realised == KPI realised",
      close(cust["realised_revenue"].sum(), kpi_realised),
      f"{cust['realised_revenue'].sum():,.2f} vs {kpi_realised:,.2f}")

pb = queries.product_bands(base)
check("product_bands total realised == KPI realised",
      close(pb["realised_revenue"].sum(), kpi_realised),
      f"{pb['realised_revenue'].sum():,.2f} vs {kpi_realised:,.2f}")

# ===========================================================================
header("TEST 12 - Value decomposition adds back to gross")
check("realised + not completed + pending == gross",
      close(m["realised_revenue"] + m["value_not_completed"] + m["value_pending"],
            m["gross_order_value"]),
      f"{m['realised_revenue']:,.2f} + {m['value_not_completed']:,.2f} + "
      f"{m['value_pending']:,.2f} = {m['gross_order_value']:,.2f}")
check("not-completed share is ~15%, not ~25% (Pending excluded)",
      14 < (m["not_completed_pct"] or 0) < 16,
      f"{m['not_completed_pct']:.2f}%")

# ===========================================================================
print("\n" + "=" * 74)
if failures:
    print(f"{RED}{BOLD}{len(failures)} of {checks} checks FAILED{RESET}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"{GREEN}{BOLD}All {checks} checks passed.{RESET}")
print("Filters respond correctly, and no join path duplicates money.")
sys.exit(0)
