"""Unit tests for the SQL helpers in dashboard/database.py.

These need no database connection, so they run instantly and are the right place
to pin down the two pieces of logic that are easy to get subtly wrong:

* the safe ``IN (...)`` predicate builder, and
* the bare-percent escaper that PyMySQL's ``%s`` substitution requires.

Run with::

    python scripts/test_sql_helpers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard.database import _escape_bare_percent, in_clause, in_predicate  # noqa: E402

GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
Q = "'"

failures: list[str] = []
checks = 0


def eq(label: str, got: object, want: object) -> None:
    global checks
    checks += 1
    if got == want:
        print(f"  {GREEN}PASS{RESET}  {label}")
    else:
        print(f"  {RED}FAIL{RESET}  {label}")
        print(f"        want {want!r}")
        print(f"        got  {got!r}")
        failures.append(label)


def raises(label: str, fn, exc) -> None:
    global checks
    checks += 1
    try:
        fn()
    except exc:
        print(f"  {GREEN}PASS{RESET}  {label}")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"  {RED}FAIL{RESET}  {label}  (raised {type(exc).__name__})")
        failures.append(label)
        return
    print(f"  {RED}FAIL{RESET}  {label}  (nothing raised)")
    failures.append(label)


# ---------------------------------------------------------------- in_clause
print(f"\n{BOLD}in_clause / in_predicate{RESET}")
print("-" * 70)

eq("single value", in_clause(["Lahore"]), ("IN (%s)", ["Lahore"]))
eq("two values", in_clause(["Lahore", "Karachi"]), ("IN (%s, %s)", ["Lahore", "Karachi"]))
eq("empty list means no filter", in_clause([]), ("1 = 1", []))
eq("None means no filter", in_clause(None), ("1 = 1", []))
eq("empty strings are dropped",
   in_clause(["Lahore", "", None]), ("IN (%s)", ["Lahore"]))

eq("predicate prefixes the column", in_predicate("o.status", ["Completed"]),
   ("o.status IN (%s)", ["Completed"]))
eq("predicate is bare-true when empty", in_predicate("o.status", []), ("1 = 1", []))

# The point of the empty case: `IN ()` is a syntax error in MySQL.
eq("never emits an empty IN list", "IN ()" in in_clause([])[0], False)


# ------------------------------------------------------- percent escaping
print(f"\n{BOLD}_escape_bare_percent (PyMySQL substitutes with 'query %% args'){RESET}")
print("-" * 70)

eq("a real placeholder is left alone",
   _escape_bare_percent("SELECT 1 WHERE a=%s", True), "SELECT 1 WHERE a=%s")
eq("several placeholders are left alone",
   _escape_bare_percent("WHERE a=%s AND b=%s", True), "WHERE a=%s AND b=%s")
eq("DATE_FORMAT's %Y and %m are escaped",
   _escape_bare_percent(f"SELECT DATE_FORMAT(d, {Q}%Y-%m{Q}) FROM t WHERE x=%s", True),
   f"SELECT DATE_FORMAT(d, {Q}%%Y-%%m{Q}) FROM t WHERE x=%s")
eq("arithmetic division is untouched",
   _escape_bare_percent("SELECT 100*x/100 WHERE y=%s", True),
   "SELECT 100*x/100 WHERE y=%s")
eq("a LIKE placeholder is untouched",
   _escape_bare_percent("WHERE name LIKE %s", True), "WHERE name LIKE %s")
eq("a percent inside a string literal is escaped",
   _escape_bare_percent(f"SELECT {Q}a%b{Q} FROM t", True), f"SELECT {Q}a%%b{Q} FROM t")
eq("a trailing percent is escaped", _escape_bare_percent("SELECT 50%", True), "SELECT 50%%")
eq("an already-escaped percent is not doubled again",
   _escape_bare_percent("SELECT 50%%", True), "SELECT 50%%")
eq("a non-%s specifier is escaped, not consumed",
   _escape_bare_percent("SELECT %d", True), "SELECT %%d")
eq("text after a bare percent survives",
   _escape_bare_percent(f"{Q}%Y-%m-%d{Q}", True), f"{Q}%%Y-%%m-%%d{Q}")
eq("a query with no percent is unchanged",
   _escape_bare_percent("SELECT 1 FROM t", True), "SELECT 1 FROM t")

# ---------------------------------------------------------------------------
# Escaping must not change the meaning of a correctly-formed query: the number
# of %s placeholders must be identical before and after.
# ---------------------------------------------------------------------------
print(f"\n{BOLD}placeholder count is preserved{RESET}")
print("-" * 70)

for label, sql in [
    ("3 placeholders", "SELECT * FROM t WHERE a=%s AND b=%s AND c=%s"),
    ("2 placeholders + DATE_FORMAT",
     f"SELECT DATE_FORMAT(d, {Q}%Y{Q}), %s FROM t WHERE x=%s"),
    ("no placeholders", "SELECT COUNT(*) FROM t"),
]:
    before = sql.count("%s")
    after = _escape_bare_percent(sql, True).count("%s")
    eq(f"{label}: {before} -> {after}", after, before)

# ---------------------------------------------------------------------------
# Guard: the escaper must be pure. It must never mutate its input.
# ---------------------------------------------------------------------------
print(f"\n{BOLD}purity{RESET}")
print("-" * 70)
original = f"SELECT DATE_FORMAT(d, {Q}%Y{Q}) FROM t WHERE x=%s"
copy = str(original)
_escape_bare_percent(original, True)
eq("input string is not mutated", original, copy)

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
if failures:
    print(f"{RED}{BOLD}{len(failures)} of {checks} checks FAILED{RESET}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"{GREEN}{BOLD}All {checks} SQL helper checks passed.{RESET}")
sys.exit(0)
