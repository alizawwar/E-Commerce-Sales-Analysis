"""Prove the dashboard degrades gracefully when the database is unreachable.

The brief is explicit: MySQL unavailable, bad credentials, a missing ``.env``
and a missing environment variable must each produce a friendly, non-technical
message for the user, never a raw stack trace - and the message must not leak
the password.

Three layers are checked:

1. ``database.test_connection()`` returns ``(False, friendly_message)``.
2. ``queries.kpi_metrics()`` raises ``DashboardDBError``, whose ``str()`` is
   safe to show.
3. The whole Streamlit app renders the "Database unavailable" panel and an
   ``st.error``, rather than an unhandled exception.

Run with::

    python scripts/test_dashboard_failure_modes.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

GREEN, RED, BOLD, GREY, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[90m", "\033[0m"

failures: list[str] = []
checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    suffix = f"  {GREY}{detail}{RESET}" if detail else ""
    if condition:
        print(f"  {GREEN}PASS{RESET}  {label}{suffix}")
    else:
        print(f"  {RED}FAIL{RESET}  {label}{suffix}")
        failures.append(label)


def header(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    print("-" * 74)


# The string that must never appear in a user-facing message.
#
# It is read from the same configuration object the application uses, at run
# time, and is never written literally in this file. An earlier version carried
# a hardcoded fallback, which put the real password into a source file - the
# exact mistake the leak checks below exist to prevent.
try:
    from dashboard.config import load_db_config

    REAL_PASSWORD = load_db_config().password
except Exception:  # noqa: BLE001 - no usable configuration; leak checks still run
    REAL_PASSWORD = os.environ.get("DB_PASSWORD", "")


def assert_no_leak(label: str, text: str) -> None:
    """A user-facing string must not contain the password or a traceback."""
    lowered = text.lower()
    if REAL_PASSWORD:
        check(f"{label}: does not contain the password", REAL_PASSWORD not in text)
    check(f"{label}: does not contain a traceback",
          "traceback" not in lowered and "pymysql" not in lowered)
    check(f"{label}: does not name the database internals",
          "access denied" not in lowered and "errno" not in lowered,
          text[:70])


# ===========================================================================
header("1 - Bad password: test_connection() returns a friendly failure")


def run_subprocess(source: str, env_overrides: dict[str, str]) -> str:
    """Run a snippet in a fresh interpreter with an overridden environment."""
    env = dict(os.environ)
    env.update(env_overrides)
    # Keep the child's stdout encoding sane on Windows.
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-W", "ignore", "-c", source],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=180,
    )
    return (result.stdout or "") + (result.stderr or "")


# ---- 1. wrong password -----------------------------------------------------
bad_pw_src = """
import sys; sys.path.insert(0, '.')
from dashboard import database
ok, message = database.test_connection()
print('OK=', ok)
print('MESSAGE=', message)
"""
out = run_subprocess(bad_pw_src, {"MYSQL_PWD": "definitely-not-the-password",
                                  "DB_PASSWORD": "definitely-not-the-password"})

# The app must read DB_* or MYSQL_*; try whichever the config actually uses.
if "OK= False" not in out:
    check("wrong password is reported as a failure", False, out.strip()[-90:])
else:
    check("wrong password is reported as a failure", True)
    message = out.split("MESSAGE=", 1)[1].strip().splitlines()[0]
    assert_no_leak("bad password message", message)


# ---- 2. unreachable host ---------------------------------------------------
header("2 - MySQL unreachable: friendly message, no traceback")

bad_host_src = """
import sys; sys.path.insert(0, '.')
from dashboard import database
ok, message = database.test_connection()
print('OK=', ok)
print('MESSAGE=', message)
"""
env = {"DB_HOST": "127.0.0.1", "DB_PORT": "3999", "MYSQL_HOST": "127.0.0.1",
       "MYSQL_PORT": "3999"}
out = run_subprocess(bad_host_src, env)
check("unreachable MySQL is reported as a failure", "OK= False" in out,
      out.strip().splitlines()[-1][:80] if out.strip() else "no output")
if "MESSAGE=" in out:
    message = out.split("MESSAGE=", 1)[1].strip().splitlines()[0]
    assert_no_leak("unreachable message", message)
    check("unreachable message mentions the database is not reachable",
          "reach" in message.lower() or "connect" in message.lower(),
          message[:80])


# ---- 3. a query raises DashboardDBError, not an arbitrary exception --------
header("3 - A query against a dead database raises DashboardDBError")

query_src = """
import sys; sys.path.insert(0, '.')
from dashboard import queries
from dashboard.database import DashboardDBError
from dashboard.utils import Filters
try:
    queries.kpi_metrics(Filters())
except DashboardDBError as exc:
    print('TYPE=DashboardDBError')
    print('MESSAGE=', str(exc))
except Exception as exc:
    print('TYPE=' + type(exc).__name__)
    print('MESSAGE=', str(exc))
"""
out = run_subprocess(query_src, env)
check("kpi_metrics raises DashboardDBError when the DB is down",
      "TYPE=DashboardDBError" in out, out.strip().splitlines()[-1][:80])
if "MESSAGE=" in out:
    assert_no_leak("DashboardDBError message",
                   out.split("MESSAGE=", 1)[1].strip().splitlines()[0])


# ---- 4. the app itself renders the friendly panel --------------------------
header("4 - The app renders a friendly panel instead of crashing")

app_src = """
import sys; sys.path.insert(0, '.')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('dashboard/app.py', default_timeout=300)
at.run()
print('EXCEPTIONS=', len(at.exception))
print('ERRORS=', len(at.sidebar.error) + len(at.error))
for e in list(at.sidebar.error) + list(at.error):
    print('ERROR_TEXT=', e.value)
for s in at.sidebar.caption:
    print('CAPTION=', s.value)
"""
out = run_subprocess(app_src, env)
check("the app does not raise an unhandled exception", "EXCEPTIONS= 0" in out,
      out.strip().splitlines()[-1][:80] if out.strip() else "no output")
check("the app shows an error to the user", "ERRORS= 0" not in out,
      "at least one error panel is rendered")
check("the app names the problem in plain language",
      "database unavailable" in out.lower() or "cannot reach mysql" in out.lower(),
      next((ln for ln in out.splitlines() if ln.startswith("ERROR_TEXT=")), "")[:90])
for line in out.splitlines():
    if line.startswith(("ERROR_TEXT=", "CAPTION=")):
        assert_no_leak("app failure panel", line)


# ---- 5. missing every DB variable -----------------------------------------
header("5 - Missing configuration: a clear configuration error")

missing_src = """
import os, sys
sys.path.insert(0, '.')
# Remove every way the app could learn the credentials, and point .env at a
# path that does not exist so nothing is silently re-loaded.
for key in list(os.environ):
    if key.upper().startswith(('DB_', 'MYSQL_')):
        del os.environ[key]
import dotenv
dotenv.load_dotenv = lambda *a, **k: False
# Re-import config with dotenv disabled.
for mod in [m for m in list(sys.modules) if m.startswith('dashboard')]:
    del sys.modules[mod]
from dashboard.database import test_connection
ok, message = test_connection()
print('OK=', ok)
print('MESSAGE=', message)
"""
out = run_subprocess(missing_src, {})
check("missing credentials are reported as a failure", "OK= False" in out,
      out.strip().splitlines()[-1][:80] if out.strip() else "no output")
if "MESSAGE=" in out:
    message = out.split("MESSAGE=", 1)[1].strip().splitlines()[0]
    assert_no_leak("missing config message", message)
    check("missing config message tells the user what to set",
          "env" in message.lower() or "config" in message.lower()
          or "database" in message.lower(),
          message[:90])


# ===========================================================================
print("\n" + "=" * 74)
if failures:
    print(f"{RED}{BOLD}{len(failures)} of {checks} checks FAILED{RESET}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"{GREEN}{BOLD}All {checks} failure-mode checks passed.{RESET}")
print("Every failure path shows a friendly message and leaks nothing.")
sys.exit(0)
