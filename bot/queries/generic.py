"""Schema introspection and generic table browsing.

All queries use ``information_schema`` and are inherently read-only.
"""

from __future__ import annotations

import logging
import re

from bot import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table listing
# ---------------------------------------------------------------------------

_LIST_TABLES_SQL = """
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
"""


async def list_tables() -> list[str]:
    """Return all public base-table names."""
    rows = await db.fetch(_LIST_TABLES_SQL)
    return [r["table_name"] for r in rows]


# ---------------------------------------------------------------------------
# Describe table
# ---------------------------------------------------------------------------

_DESCRIBE_SQL = """
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = $1
ORDER BY ordinal_position;
"""

_INDEXES_SQL = """
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = $1
ORDER BY indexname;
"""


async def describe_table(table: str) -> tuple[list[dict], list[dict]]:
    """Return (columns, indexes) for *table*.

    Each column dict: {name, type, nullable, default}.
    Each index dict: {name, definition}.
    """
    if not _safe_identifier(table):
        return [], []

    col_rows = await db.fetch(_DESCRIBE_SQL, table)
    columns = [
        {
            "name": r["column_name"],
            "type": r["data_type"],
            "nullable": r["is_nullable"],
            "default": r["column_default"],
        }
        for r in col_rows
    ]

    idx_rows = await db.fetch(_INDEXES_SQL, table)
    indexes = [
        {"name": r["indexname"], "definition": r["indexdef"]}
        for r in idx_rows
    ]

    return columns, indexes


# ---------------------------------------------------------------------------
# Browse table rows
# ---------------------------------------------------------------------------


async def browse_table(
    table: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[str], list[list], int | None]:
    """Return (headers, rows, total_count) for *table*.

    Uses a safe identifier check before interpolating the table name (which
    cannot be parameterised in SQL).
    """
    if not _safe_identifier(table):
        return [], [], 0

    count_val = await db.fetchval(
        f'SELECT count(*) FROM "{table}"'  # noqa: S608
    )
    total = int(count_val) if count_val is not None else None

    data_rows = await db.fetch(
        f'SELECT * FROM "{table}" ORDER BY 1 DESC LIMIT $1 OFFSET $2',  # noqa: S608
        limit,
        offset,
    )

    if not data_rows:
        return [], [], total

    headers = list(data_rows[0].keys())
    rows = [list(r.values()) for r in data_rows]
    return headers, rows, total


# ---------------------------------------------------------------------------
# Column introspection helpers (used by domain modules)
# ---------------------------------------------------------------------------


async def get_columns(table: str) -> list[str]:
    """Return column names for *table*."""
    rows = await db.fetch(_DESCRIBE_SQL, table)
    return [r["column_name"] for r in rows]


async def table_exists(table: str) -> bool:
    """Check whether *table* exists in the public schema."""
    if not _safe_identifier(table):
        return False
    val = await db.fetchval(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=$1",
        table,
    )
    return val is not None


# ---------------------------------------------------------------------------
# SQL safety
# ---------------------------------------------------------------------------

_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _safe_identifier(name: str) -> bool:
    """Return True if *name* looks like a safe SQL identifier."""
    return bool(_IDENT_RE.match(name))


# Blocked keywords for raw-query validation
_BLOCKED_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "COPY",
    "EXECUTE",
}


def validate_select(sql: str) -> str | None:
    """Validate a user-supplied SQL string.

    Returns an error message, or None if valid.
    """
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        return "Only SELECT statements are allowed."
    if ";" in stripped:
        return "Semicolons are not allowed."
    upper = stripped.upper()
    for kw in _BLOCKED_KEYWORDS:
        # Match whole word only
        if re.search(rf"\b{kw}\b", upper):
            return f"Keyword {kw} is not allowed."
    return None


def ensure_limit(sql: str, max_rows: int = 100) -> str:
    """Append LIMIT if not already present."""
    if "LIMIT" not in sql.upper():
        return sql.rstrip().rstrip(";") + f" LIMIT {max_rows}"
    return sql
