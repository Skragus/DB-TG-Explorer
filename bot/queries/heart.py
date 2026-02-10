"""Heart rate data queries with auto-detected table/column mapping."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bot import db
from bot.queries.generic import get_columns, table_exists

logger = logging.getLogger(__name__)

TABLE_CANDIDATES = [
    "heart_rate_daily",
    "heart_rate_samples",
    "heart_rate",
    "heartrate",
    "hr_data",
]

_DATE_CANDIDATES = ["date", "measured_at", "timestamp", "created_at", "time", "day"]
_VALUE_CANDIDATES = ["bpm", "heart_rate", "avg_bpm", "value", "resting_hr", "avg_hr"]
_MIN_CANDIDATES = ["min_bpm", "min_hr", "resting_hr"]
_MAX_CANDIDATES = ["max_bpm", "max_hr"]

_table: str | None = None
_date_col: str | None = None
_value_col: str | None = None
_min_col: str | None = None
_max_col: str | None = None


async def init() -> bool:
    global _table, _date_col, _value_col, _min_col, _max_col  # noqa: PLW0603
    for t in TABLE_CANDIDATES:
        if await table_exists(t):
            _table = t
            break
    if _table is None:
        logger.warning("No heart-rate table found among candidates: %s", TABLE_CANDIDATES)
        return False

    cols = await get_columns(_table)
    _date_col = _first_match(cols, _DATE_CANDIDATES)
    _value_col = _first_match(cols, _VALUE_CANDIDATES)
    _min_col = _first_match(cols, _MIN_CANDIDATES)
    _max_col = _first_match(cols, _MAX_CANDIDATES)

    if not _date_col or not _value_col:
        logger.warning("Heart table %s: could not resolve columns from %s", _table, cols)
        return False

    logger.info("Heart: table=%s date=%s value=%s", _table, _date_col, _value_col)
    return True


def available() -> bool:
    return _table is not None and _date_col is not None and _value_col is not None


async def latest() -> dict[str, Any] | None:
    if not available():
        return None
    row = await db.fetchrow(
        f'SELECT * FROM "{_table}" ORDER BY "{_date_col}" DESC LIMIT 1'  # noqa: S608
    )
    return dict(row) if row else None


async def today_summary(start_utc: datetime, end_utc: datetime) -> dict[str, Any] | None:
    """Aggregated heart summary for a UTC range."""
    if not available():
        return None
    row = await db.fetchrow(
        f'SELECT AVG("{_value_col}") AS avg_bpm, '  # noqa: S608
        f'MIN("{_value_col}") AS min_bpm, '
        f'MAX("{_value_col}") AS max_bpm, '
        f'COUNT(*) AS samples '
        f'FROM "{_table}" '
        f'WHERE "{_date_col}" >= $1 AND "{_date_col}" < $2',
        start_utc,
        end_utc,
    )
    if row and row["samples"]:
        return dict(row)
    return None


async def recent(limit: int = 14, offset: int = 0) -> list[dict[str, Any]]:
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


async def sparkline_values(n: int = 30) -> list[float | None]:
    if not available():
        return []
    rows = await db.fetch(
        f'SELECT "{_value_col}" FROM "{_table}" ORDER BY "{_date_col}" DESC LIMIT $1',  # noqa: S608
        n,
    )
    return [float(r[_value_col]) if r[_value_col] is not None else None for r in reversed(rows)]


def date_col() -> str:
    return _date_col or "date"

def value_col() -> str:
    return _value_col or "bpm"


def _first_match(available_cols: list[str], candidates: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in available_cols}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None
