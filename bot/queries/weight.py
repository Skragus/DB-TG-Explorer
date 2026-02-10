"""Weight data queries with auto-detected table/column mapping."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bot import db
from bot.queries.generic import get_columns, table_exists

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table / column candidates
# ---------------------------------------------------------------------------

TABLE_CANDIDATES = [
    "measurements_weight",
    "weight",
    "weight_measurements",
    "body_weight",
]

# Semantic columns we look for
_DATE_CANDIDATES = ["date", "measured_at", "timestamp", "created_at", "time"]
_VALUE_CANDIDATES = ["weight_kg", "weight", "value", "kg"]
_SOURCE_CANDIDATES = ["source", "data_source", "origin"]

# Resolved mapping (filled at init)
_table: str | None = None
_date_col: str | None = None
_value_col: str | None = None
_source_col: str | None = None


async def init() -> bool:
    """Detect table and columns.  Returns True if ready."""
    global _table, _date_col, _value_col, _source_col  # noqa: PLW0603

    for t in TABLE_CANDIDATES:
        if await table_exists(t):
            _table = t
            break
    if _table is None:
        logger.warning("No weight table found among candidates: %s", TABLE_CANDIDATES)
        return False

    cols = await get_columns(_table)
    _date_col = _first_match(cols, _DATE_CANDIDATES)
    _value_col = _first_match(cols, _VALUE_CANDIDATES)
    _source_col = _first_match(cols, _SOURCE_CANDIDATES)

    if not _date_col or not _value_col:
        logger.warning("Weight table %s: could not resolve date/value columns from %s", _table, cols)
        return False

    logger.info("Weight: table=%s date=%s value=%s source=%s", _table, _date_col, _value_col, _source_col)
    return True


def available() -> bool:
    return _table is not None and _date_col is not None and _value_col is not None


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


async def latest() -> dict[str, Any] | None:
    """Return the most recent weight record."""
    if not available():
        return None
    row = await db.fetchrow(
        f'SELECT * FROM "{_table}" ORDER BY "{_date_col}" DESC LIMIT 1'  # noqa: S608
    )
    return dict(row) if row else None


async def recent(limit: int = 14, offset: int = 0) -> list[dict[str, Any]]:
    """Return recent weight records."""
    if not available():
        return []
    rows = await db.fetch(
        f'SELECT * FROM "{_table}" ORDER BY "{_date_col}" DESC LIMIT $1 OFFSET $2',  # noqa: S608
        limit,
        offset,
    )
    return [dict(r) for r in rows]


async def count() -> int:
    if not available():
        return 0
    val = await db.fetchval(f'SELECT count(*) FROM "{_table}"')  # noqa: S608
    return int(val) if val else 0


async def in_range(start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Records in a UTC datetime range."""
    if not available():
        return []
    rows = await db.fetch(
        f'SELECT * FROM "{_table}" WHERE "{_date_col}" >= $1 AND "{_date_col}" < $2 '  # noqa: S608
        f'ORDER BY "{_date_col}" ASC',
        start,
        end,
    )
    return [dict(r) for r in rows]


async def trend_averages(recent_days: int = 7) -> tuple[float | None, float | None]:
    """Return (recent_avg, previous_avg) for trend comparison.

    recent = last *recent_days* entries, previous = the *recent_days* before that.
    """
    if not available():
        return None, None
    rows = await db.fetch(
        f'SELECT "{_value_col}" FROM "{_table}" ORDER BY "{_date_col}" DESC LIMIT $1',  # noqa: S608
        recent_days * 2,
    )
    if not rows:
        return None, None
    values = [float(r[_value_col]) for r in rows if r[_value_col] is not None]
    if len(values) <= recent_days:
        return _avg(values), None
    return _avg(values[:recent_days]), _avg(values[recent_days:])


async def sparkline_values(n: int = 30) -> list[float | None]:
    """Return last *n* values ordered oldest-first for sparkline."""
    if not available():
        return []
    rows = await db.fetch(
        f'SELECT "{_value_col}" FROM "{_table}" ORDER BY "{_date_col}" DESC LIMIT $1',  # noqa: S608
        n,
    )
    return [float(r[_value_col]) if r[_value_col] is not None else None for r in reversed(rows)]


# ---------------------------------------------------------------------------
# Column accessors (used by handlers for display)
# ---------------------------------------------------------------------------

def date_col() -> str:
    return _date_col or "date"

def value_col() -> str:
    return _value_col or "weight_kg"


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _first_match(available_cols: list[str], candidates: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in available_cols}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def _avg(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None
