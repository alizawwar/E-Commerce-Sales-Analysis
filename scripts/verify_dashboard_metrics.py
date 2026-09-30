"""Reconcile the dashboard's own queries against the Phase 3 SQL results.

This is the Phase 4 equivalent of ``sql/13_phase2_reconciliation.sql``. It calls
the *dashboard's* functions - not a re-implementation - with the default filter
selection, and compares the result to the recorded Phase 3 figures.

Run it any time you change a query::

    python scripts/verify_dashboard_metrics.py

Exit code 0 means every metric is inside its Phase 3 tolerance.
"""

from __future__ import annotations

import sys
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
from dashboard.phase3_reference import (  # noqa: E402
    PHASE3_CATEGORY_REVENUE,
    PHASE3_HEADLINE,
)
from dashboard.utils import Filters, order_status_order  # noqa: E402

GREEN, RED, YELLOW, GREY, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m"


def main() -> int:
    filters = Filters()  # default = full dataset, every status
    print("=" * 78)
    print("DASHBOARD vs PHASE 3 RECONCILIATION")
    print("=" * 78)
    print(f"Filters: dates {filters.date_from} to {filters.date_to}, "
          f"statuses {order_status_order(filters.statuses)}, no other narrowing\n")

    kpi = queries.kpi_metrics(filters)
    if not kpi:
        print(f"{RED}No KPI row returned - is the database loaded?{RESET}")
        return 2

    m = build_metric_bundle(kpi)

    # registered / inactive customers live in customer_metrics, and the
    # catalogue size is a dataset fact rather than a filtered one.
    cm = queries.customer_metrics(filters)
    if cm:
        m["registered_customers"] = cm.get("registered_customers")
        m["inactive_customers"] = cm.get("inactive_customers")
        active = cm.get("active_customers") or 0
        m["repeat_customer_rate"] = (
            100 * (cm.get("repeat_customers") or 0) / active if active else None
        )
    ds = queries.dataset_summary()
    if ds:
        m["products"] = ds.get("products")

    m["value_not_completed_pct"] = m.get("not_completed_pct")

    conc = queries.concentration(filters)
    if conc:
        m["top_10_share_pct"] = conc.get("top_10_share_pct")

    # ---------------- headline metrics
    print(f"{'Metric':<34}{'Phase 3':>16}{'Dashboard':>16}{'Diff':>10}  Result")
    print("-" * 78)
    failures: list[str] = []
    for name, (expected, tol, note) in PHASE3_HEADLINE.items():
        actual = m.get(name)
        if actual is None:
            print(f"{name:<34}{expected:>16,.2f}{'n/a':>16}{'-':>10}  {YELLOW}NO VALUE{RESET}")
            failures.append(name)
            continue
        diff = abs(float(actual) - expected)
        ok = diff <= tol
        colour = GREEN if ok else RED
        mark = "OK" if ok else "MISMATCH"
        print(f"{name:<34}{expected:>16,.2f}{float(actual):>16,.2f}{diff:>10,.4f}  {colour}{mark}{RESET}")
        if not ok:
            failures.append(f"{name} (expected {expected}, got {actual}, tol {tol}) {GREY}{note}{RESET}")

    # ---------------- category revenue
    print("\n" + "-" * 78)
    print("Category realised revenue")
    print("-" * 78)
    cats = queries.category_breakdown(filters)
    if cats.empty:
        failures.append("category_breakdown returned nothing")
    else:
        got = dict(zip(cats["category"], cats["realised_revenue"]))
        for name, expected in PHASE3_CATEGORY_REVENUE.items():
            actual = got.get(name)
            if actual is None:
                print(f"{name:<24}{expected:>18,.2f}{'missing':>18}  {YELLOW}MISSING{RESET}")
                failures.append(f"category {name} missing")
                continue
            diff = abs(float(actual) - expected)
            ok = diff <= 0.01
            colour = GREEN if ok else RED
            print(f"{name:<24}{expected:>18,.2f}{float(actual):>18,.2f}{diff:>10,.4f}  "
                  f"{colour}{'OK' if ok else 'MISMATCH'}{RESET}")
            if not ok:
                failures.append(f"category {name} expected {expected}, got {actual}")

    # ---------------- summary
    print("\n" + "=" * 78)
    if failures:
        print(f"{RED}{len(failures)} MISMATCH(ES){RESET}")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{GREEN}All {len(PHASE3_HEADLINE)} headline metrics and "
          f"{len(PHASE3_CATEGORY_REVENUE)} category revenues match Phase 3.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
