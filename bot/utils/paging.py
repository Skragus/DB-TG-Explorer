"""Compact pagination encoding for Telegram callback_data.

Telegram limits callback_data to 64 bytes.  We encode pagination state as::

    p:<module>:<offset>[:<extra>]

Examples::

    p:wt:0        – weight, page 0
    p:brw:20:steps_daily  – browse table, offset 20, table name
"""

from __future__ import annotations

SEPARATOR = ":"
PREFIX = "p"


def encode(module: str, offset: int, extra: str = "") -> str:
    """Build a callback_data string for pagination."""
    parts = [PREFIX, module, str(offset)]
    if extra:
        parts.append(extra)
    return SEPARATOR.join(parts)


def decode(data: str) -> tuple[str, int, str]:
    """Parse a callback_data string.

    Returns (module, offset, extra).
    """
    parts = data.split(SEPARATOR)
    # parts[0] == PREFIX
    module = parts[1] if len(parts) > 1 else ""
    offset = int(parts[2]) if len(parts) > 2 else 0
    extra = parts[3] if len(parts) > 3 else ""
    return module, offset, extra
