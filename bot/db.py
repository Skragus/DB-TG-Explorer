"""Async PostgreSQL connection pool and query helpers.

Every query goes through the helpers here so we get:
- consistent error handling (no crashes on DB outage)
- automatic last-query timestamp tracking for /health
- parameterised queries only (no string interpolation)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Module-level state ----------------------------------------------------------

_pool: asyncpg.Pool | None = None
last_successful_query: datetime | None = None


# Lifecycle -------------------------------------------------------------------


async def create_pool(dsn: str, *, min_size: int = 2, max_size: int = 5) -> asyncpg.Pool:
    """Create (or replace) the global connection pool."""
    global _pool  # noqa: PLW0603
    _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    logger.info("Database pool created (min=%d, max=%d)", min_size, max_size)
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool."""
    global _pool  # noqa: PLW0603
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> asyncpg.Pool:
    """Return the current pool or raise if not initialised."""
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool


# Query helpers ---------------------------------------------------------------

def _touch() -> None:
    global last_successful_query  # noqa: PLW0603
    last_successful_query = datetime.now(timezone.utc)


async def fetch(query: str, *args: Any, timeout: float = 10.0) -> list[asyncpg.Record]:
    """Run a SELECT and return a list of Record rows."""
    pool = get_pool()
    try:
        rows = await pool.fetch(query, *args, timeout=timeout)
        _touch()
        return rows
    except Exception:
        logger.exception("DB fetch error")
        raise


async def fetchrow(query: str, *args: Any, timeout: float = 10.0) -> asyncpg.Record | None:
    """Run a query and return the first row, or None."""
    pool = get_pool()
    try:
        row = await pool.fetchrow(query, *args, timeout=timeout)
        _touch()
        return row
    except Exception:
        logger.exception("DB fetchrow error")
        raise


async def fetchval(query: str, *args: Any, timeout: float = 10.0) -> Any:
    """Run a query and return a single scalar value."""
    pool = get_pool()
    try:
        val = await pool.fetchval(query, *args, timeout=timeout)
        _touch()
        return val
    except Exception:
        logger.exception("DB fetchval error")
        raise


async def execute_readonly(query: str, *args: Any, timeout: float = 10.0) -> list[asyncpg.Record]:
    """Execute an arbitrary SELECT inside a READ ONLY transaction.

    Used by the advanced query builder to add an extra safety net.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True):
            rows = await conn.fetch(query, *args, timeout=timeout)
            _touch()
            return rows


async def health_check() -> bool:
    """Return True if the pool can execute a trivial query."""
    try:
        await fetchval("SELECT 1", timeout=3.0)
        return True
    except Exception:
        return False
