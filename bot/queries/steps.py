"""Steps data queries with auto-detected table/column mapping."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bot import db
from bot.queries.generic import get_columns, table_exists

logger = logging.getLogger(__name__)

TABLE_CANDIDATES = [
    "steps_daily",
    "steps",
    "daily_steps",
    "activity_steps",
]

_DATE_CANDIDATES = ["date", "measured_at", "timestamp", "created_at", "day"]
_VALUE_CANDIDATES = ["steps", "step_count", "value", "total_steps"]
_SOURCE_CANDIDATES = ["source", "data_source", "origin"]

_table: str | None = None
_date_col: str | None = None
_value_col: str | None = None
_source_col: str | None = None


async def init() -> bool:
    global _table, _date_col, _value_col, _source_col  # noqa: PLW0603
    for t in TABLE_CANDIDATES:
        if await table_exists(t):
            _table = t
            break
    if _table is None:
        logger.warning("No steps table found among candidates: %s", TABLE_CANDIDATES)
        return False

    cols = await get_columns(_table)
    _date_col = _first_match(cols, _DATE_CANDIDATES)
    _value_col = _first_match(cols, _VALUE_CANDIDATES)
    _source_col = _first_match(cols, _SOURCE_CANDIDATES)

    if not _date_col or not _value_col:
        logger.warning("Steps table %s: could not resolve date/value columns from %s", _table, cols)
        return False

    logger.info("Steps: table=%s date=%s value=%s", _table, _date_col, _value_col)
    return True


def available() -> bool:
    return _table is not None and _date_col is not None and _value_col is not None


async def today_steps(start_utc: datetime, end_utc: datetime) -> int | None:
    if not available():
        return None
    val = await db.fetchval(
        f'SELECT SUM("{_value_col}") FROM "{_table}" '  # noqa: S608
        f'WHERE "{_date_col}" >= $1 AND "{_date_col}" < $2',
        start_utc,
        end_utc,
    )
    return int(val) if val is not None else None


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


async def avg_steps(days: int, start_utc: datetime) -> float | None:
    """Average daily steps over *days* before *start_utc*."""
    if not available():
        return None
    val = await db.fetchval(
        f'SELECT AVG("{_value_col}") FROM "{_table}" '  # noqa: S608
        f'WHERE "{_date_col}" >= $1',
        start_utc,
    )
    return float(val) if val is not None else None


async def total_steps(start_utc: datetime) -> int | None:
    if not available():
        return None
    val = await db.fetchval(
        f'SELECT SUM("{_value_col}") FROM "{_table}" '  # noqa: S608
        f'WHERE "{_date_col}" >= $1',
        start_utc,
    )
    return int(val) if val is not None else None


async def in_range(start: datetime, end: datetime) -> list[dict[str, Any]]:
    if not available():
        return []
    rows = await db.fetch(
        f'SELECT * FROM "{_table}" WHERE "{_date_col}" >= $1 AND "{_date_col}" < $2 '  # noqa: S608
        f'ORDER BY "{_date_col}" ASC',
        start,
        end,
    )
    return [dict(r) for r in rows]


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
    return _value_col or "steps"


def _first_match(available_cols: list[str], candidates: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in available_cols}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None
