"""Sleep data queries with auto-detected table/column mapping."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bot import db
from bot.queries.generic import get_columns, table_exists

logger = logging.getLogger(__name__)

TABLE_CANDIDATES = [
    "sleep_sessions",
    "sleep",
    "sleep_data",
    "sleep_records",
]

_START_CANDIDATES = ["start", "start_time", "sleep_start", "bedtime", "started_at"]
_END_CANDIDATES = ["end", "end_time", "sleep_end", "wake_time", "ended_at"]
_DURATION_CANDIDATES = ["duration", "duration_minutes", "total_minutes", "sleep_duration"]
_STAGES_CANDIDATES = ["stages", "stages_summary", "sleep_stages"]
_DATE_CANDIDATES = ["date", "night", "created_at"]

_table: str | None = None
_start_col: str | None = None
_end_col: str | None = None
_duration_col: str | None = None
_stages_col: str | None = None
_date_col: str | None = None  # fallback ordering column


async def init() -> bool:
    global _table, _start_col, _end_col, _duration_col, _stages_col, _date_col  # noqa: PLW0603
    for t in TABLE_CANDIDATES:
        if await table_exists(t):
            _table = t
            break
    if _table is None:
        logger.warning("No sleep table found among candidates: %s", TABLE_CANDIDATES)
        return False

    cols = await get_columns(_table)
    _start_col = _first_match(cols, _START_CANDIDATES)
    _end_col = _first_match(cols, _END_CANDIDATES)
    _duration_col = _first_match(cols, _DURATION_CANDIDATES)
    _stages_col = _first_match(cols, _STAGES_CANDIDATES)
    _date_col = _first_match(cols, _DATE_CANDIDATES)

    order = _order_col()
    if order is None:
        logger.warning("Sleep table %s: no usable date/start column from %s", _table, cols)
        return False

    logger.info(
        "Sleep: table=%s start=%s end=%s dur=%s stages=%s date=%s",
        _table, _start_col, _end_col, _duration_col, _stages_col, _date_col,
    )
    return True


def available() -> bool:
    return _table is not None and _order_col() is not None


def _order_col() -> str | None:
    return _start_col or _date_col


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


async def last_night(start_utc: datetime, end_utc: datetime) -> dict[str, Any] | None:
    """Most recent sleep session ending within the given UTC range."""
    if not available():
        return None
    oc = _order_col()
    row = await db.fetchrow(
        f'SELECT * FROM "{_table}" WHERE "{oc}" >= $1 AND "{oc}" < $2 '  # noqa: S608
        f'ORDER BY "{oc}" DESC LIMIT 1',
        start_utc,
        end_utc,
    )
    return dict(row) if row else None


async def recent(limit: int = 7, offset: int = 0) -> list[dict[str, Any]]:
    if not available():
        return []
    oc = _order_col()
    rows = await db.fetch(
        f'SELECT * FROM "{_table}" ORDER BY "{oc}" DESC LIMIT $1 OFFSET $2',  # noqa: S608
        limit,
        offset,
    )
    return [dict(r) for r in rows]


async def count() -> int:
    if not available():
        return 0
    val = await db.fetchval(f'SELECT count(*) FROM "{_table}"')  # noqa: S608
    return int(val) if val else 0


async def avg_duration(start_utc: datetime) -> float | None:
    """Average duration (in the raw unit of the column) since *start_utc*."""
    if not available() or not _duration_col:
        return None
    oc = _order_col()
    val = await db.fetchval(
        f'SELECT AVG("{_duration_col}") FROM "{_table}" WHERE "{oc}" >= $1',  # noqa: S608
        start_utc,
    )
    return float(val) if val is not None else None


async def in_range(start: datetime, end: datetime) -> list[dict[str, Any]]:
    if not available():
        return []
    oc = _order_col()
    rows = await db.fetch(
        f'SELECT * FROM "{_table}" WHERE "{oc}" >= $1 AND "{oc}" < $2 '  # noqa: S608
        f'ORDER BY "{oc}" ASC',
        start,
        end,
    )
    return [dict(r) for r in rows]


# Column accessors
def start_col() -> str | None:
    return _start_col

def end_col() -> str | None:
    return _end_col

def duration_col() -> str | None:
    return _duration_col

def stages_col() -> str | None:
    return _stages_col

def order_col() -> str:
    return _order_col() or "start"


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _first_match(available_cols: list[str], candidates: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in available_cols}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None
