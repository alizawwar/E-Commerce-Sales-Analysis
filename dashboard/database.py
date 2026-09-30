"""Database access layer for the dashboard.

Design notes
------------
* **One connection per query.** A cached connection can go stale (MySQL's
  ``wait_timeout``, a service restart) and a local dashboard does not need the
  microseconds saved. What actually makes the app fast is *result* caching, which
  is done one level up in :mod:`queries`.

* **Every query is parameterised.** Values are never interpolated into SQL text.
  List filters are expanded into ``%s`` placeholders and passed as a flat
  sequence of parameters - see :func:`in_clause`. This keeps filter values out
  of the SQL string entirely, so there is no injection surface.

* **Errors are translated, not leaked.** MySQL exception text is wrapped in
  :class:`DashboardDBError` with a human message. The technical detail is
  written to a log file; the UI shows the friendly message and keeps the
  detail behind an expander for development.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import pandas as pd

from .config import PROJECT_ROOT, DatabaseConfig, load_db_config

LOG_PATH = PROJECT_ROOT / "dashboard" / "dashboard.log"
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("dashboard.db")


class DashboardDBError(RuntimeError):
    """A database problem, already phrased for a non-technical user."""


def _is_missing_module(exc: BaseException) -> bool:
    return isinstance(exc, ModuleNotFoundError) and "pymysql" in str(exc).lower()


# ---------------------------------------------------------------------------
# Connection handling
# ---------------------------------------------------------------------------
@contextmanager
def get_connection() -> Iterator[Any]:
    """Yield a live PyMySQL connection, always closing it afterwards.

    Only the *connection attempt* is wrapped into a friendly error. Anything
    raised by the caller's body inside the ``with`` block propagates untouched,
    so a genuine SQL error is never mislabelled as a connection problem.
    """
    cfg: DatabaseConfig = load_db_config()

    try:
        import pymysql  # imported lazily so the app can show a helpful message
        from pymysql.cursors import DictCursor
    except ModuleNotFoundError as exc:  # pragma: no cover - setup problem
        if _is_missing_module(exc):
            raise DashboardDBError(
                "The MySQL driver is not installed. "
                "Run: pip install -r requirements.txt"
            ) from exc
        raise

    try:
        conn = pymysql.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database=cfg.name,
            charset=cfg.charset,
            cursorclass=DictCursor,
            connect_timeout=cfg.connect_timeout,
            autocommit=True,
        )
    except Exception as exc:  # noqa: BLE001 - re-raised as a friendly error
        log.exception("Connection attempt to %s failed", cfg.label)
        code = getattr(exc, "args", [None])[0]
        if code == 1045:
            raise DashboardDBError(
                "MySQL rejected the credentials. Check DB_USER and DB_PASSWORD in your .env file."
            ) from exc
        if code in (2003, 2002):
            raise DashboardDBError(
                f"Could not reach MySQL at {cfg.host}:{cfg.port}. "
                "Is the MySQL service running?"
            ) from exc
        if code == 1049:
            raise DashboardDBError(
                f"Database '{cfg.name}' does not exist. Load it with sql/01 to sql/04."
            ) from exc
        raise DashboardDBError(
            f"Could not connect to the database ({type(exc).__name__}). "
            "See dashboard.log for details."
        ) from exc

    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - closing must never mask the real error
            log.debug("Ignoring error while closing connection", exc_info=True)


# ---------------------------------------------------------------------------
# Parameter helpers
# ---------------------------------------------------------------------------
def in_clause(values: Sequence[Any] | None) -> tuple[str, list[Any]]:
    """Build a safe ``IN (...)`` fragment.

    Returns the SQL fragment (containing only ``%s`` placeholders) and the
    matching parameter list. An empty selection means "no filter", so the
    fragment becomes a condition that is always true and the parameter list is
    empty.

    >>> frag, params = in_clause(["Lahore", "Karachi"])
    >>> frag
    'IN (%s, %s)'
    >>> params
    ['Lahore', 'Karachi']
    """
    cleaned = [v for v in (values or []) if v is not None and v != ""]
    if not cleaned:
        # `1 = 1` keeps the surrounding SQL valid without emitting `IN ()`,
        # which is a syntax error in MySQL.
        return "1 = 1", []
    placeholders = ", ".join(["%s"] * len(cleaned))
    return f"IN ({placeholders})", list(cleaned)


def in_predicate(column: str, values: Sequence[Any] | None) -> tuple[str, list[Any]]:
    """Build a complete, safe predicate for an optional list filter.

    Returns a ready-to-use SQL fragment plus its parameters. An empty selection
    means "no filter", in which case the fragment is ``1 = 1`` (always true, and
    the surrounding SQL stays valid - ``IN ()`` is a syntax error in MySQL).

    >>> frag, params = in_predicate("o.status", ["Completed"])
    >>> frag
    'o.status IN (%s)'
    >>> params
    ['Completed']
    >>> in_predicate("o.status", [])[0]
    '1 = 1'
    """
    clause, params = in_clause(values)
    if not params:
        return "1 = 1", []
    return f"{column} {clause}", params


def _normalise(value: Any) -> Any:
    """Convert DB-native types into things pandas and Streamlit render well."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


# ---------------------------------------------------------------------------
# Query execution
# ---------------------------------------------------------------------------
def _escape_bare_percent(sql: str, has_params: bool) -> str:
    """Double any ``%`` that is not already a ``%s`` placeholder.

    PyMySQL substitutes parameters with ``query % args``. A literal percent
    inside the SQL - ``DATE_FORMAT(d, '%Y-%m')`` is the easy mistake - is
    therefore read as a printf format specifier and the statement fails before
    it ever reaches MySQL.

    Doubling the bare percents makes the SQL correct for the driver while
    leaving the percent signs intact for the server, so a query containing
    ``DATE_FORMAT`` works instead of exploding. The two-character overlap in
    ``%s`` and ``%%`` is handled by walking the string rather than using a
    naive replace.

    Only applied when the query actually takes parameters; a query with no
    parameters is sent verbatim and needs no escaping.
    """
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        char = sql[i]
        if char != "%":
            out.append(char)
            i += 1
            continue
        nxt = sql[i + 1] if i + 1 < n else ""
        if nxt == "s":
            out.append("%s")          # a real placeholder, leave it alone
            i += 2
            continue
        if nxt == "%":
            out.append("%%")          # already escaped, leave it alone
            i += 2
            continue
        # A bare literal percent. Escape it and move on by exactly one
        # character, so the following text ('%Y' -> '%%Y') is preserved.
        out.append("%%")
        i += 1
    return "".join(out)


def run_query(sql: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
    """Execute a parameterised query and return a DataFrame.

    An empty result set is returned as an empty DataFrame, so downstream code
    can rely on the shape.
    """
    params = list(params or [])
    sql = _escape_bare_percent(sql, bool(params))
    started = time.perf_counter()
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
            except ValueError as exc:  # noqa: BLE001
                # PyMySQL interpolates with `query % args`, so a literal
                # percent sign in the SQL (for example DATE_FORMAT(x, '%Y'))
                # is mistaken for a format specifier and the statement never
                # reaches the server. This is a code bug, not a data problem,
                # so say so plainly.
                log.error("Parameter interpolation failed for query: %s", sql, exc_info=True)
                raise DashboardDBError(
                    "A dashboard query contained a literal '%' in its SQL text, which "
                    "conflicts with the MySQL driver's parameter substitution. "
                    "Use EXTRACT(YEAR_MONTH FROM ...) instead of DATE_FORMAT(...). "
                    "See dashboard.log."
                ) from exc
            except Exception as exc:  # noqa: BLE001
                log.error("Query failed: %s\nparams=%s", sql, params, exc_info=True)
                code = getattr(exc, "args", [None])[0]
                if code == 1062:
                    raise DashboardDBError("Duplicate key rejected by the database.") from exc
                raise DashboardDBError(
                    "The database rejected one of the dashboard queries. "
                    "See dashboard.log for the technical detail."
                ) from exc

    elapsed_ms = (time.perf_counter() - started) * 1000
    log.info("query ok in %.1f ms (%d rows)", elapsed_ms, len(rows))

    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    for column in frame.columns:
        if frame[column].map(lambda v: isinstance(v, Decimal)).any():
            frame[column] = frame[column].map(_normalise)
    return frame


def run_scalar(sql: str, params: Iterable[Any] | None = None, default: Any = None) -> Any:
    """Return the first column of the first row, or ``default`` when empty."""
    frame = run_query(sql, params)
    if frame.empty:
        return default
    return _normalise(frame.iloc[0, 0])


def test_connection() -> tuple[bool, str]:
    """Probe the database.

    Returns ``(ok, message)``. The message is safe to display and never
    contains a password.
    """
    try:
        cfg = load_db_config()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() AS v, DATABASE() AS d")
                row = cur.fetchone()
        return True, f"Connected to {row['d']} on MySQL {row['v']} as {cfg.user}."
    except DashboardDBError as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"Unexpected connection problem: {exc}"
