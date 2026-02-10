"""Output formatting utilities for Telegram messages.

All public functions return strings ready to be sent with ``parse_mode="HTML"``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Sequence
from zoneinfo import ZoneInfo

MAX_MSG_LEN = 4000  # leave margin below Telegram's 4096 limit

# ---------------------------------------------------------------------------
# Monospace table
# ---------------------------------------------------------------------------


def mono_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Render a fixed-width table inside ``<pre>`` tags.

    Columns are auto-sized.  Values are stringified and truncated per cell.
    """
    max_cell = 20

    def _cell(v: Any) -> str:
        s = _stringify(v)
        return s[:max_cell]

    str_rows = [[_cell(c) for c in row] for row in rows]
    str_headers = [h[:max_cell] for h in headers]

    # Compute column widths
    cols = len(str_headers)
    widths = [len(h) for h in str_headers]
    for row in str_rows:
        for i, c in enumerate(row):
            if i < cols:
                widths[i] = max(widths[i], len(c))

    def _fmt_row(cells: Sequence[str]) -> str:
        return " ".join(c.ljust(widths[i]) for i, c in enumerate(cells) if i < cols)

    lines = [_fmt_row(str_headers), "-" * (sum(widths) + cols - 1)]
    lines.extend(_fmt_row(r) for r in str_rows)
    table = "\n".join(lines)
    return f"<pre>{_escape_html(table)}</pre>"


# ---------------------------------------------------------------------------
# Sparkline
# ---------------------------------------------------------------------------

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values: Sequence[float | int | None]) -> str:
    """Generate an ASCII sparkline from numeric values.

    None values are rendered as a space.
    """
    nums = [v for v in values if v is not None]
    if not nums:
        return ""
    lo, hi = min(nums), max(nums)
    span = hi - lo if hi != lo else 1
    chars: list[str] = []
    for v in values:
        if v is None:
            chars.append(" ")
        else:
            idx = int((v - lo) / span * (len(SPARK_CHARS) - 1))
            chars.append(SPARK_CHARS[idx])
    return "".join(chars)


# ---------------------------------------------------------------------------
# Trend delta
# ---------------------------------------------------------------------------


def trend_delta(current: float | None, previous: float | None, unit: str = "") -> str:
    """Format a trend comparison string."""
    if current is None or previous is None:
        return "N/A"
    delta = current - previous
    arrow = "+" if delta >= 0 else ""  # minus sign is included in negative numbers
    u = f" {unit}" if unit else ""
    return f"{arrow}{delta:.1f}{u}  (avg {current:.1f} vs {previous:.1f})"


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------


def truncate(text: str, max_len: int = MAX_MSG_LEN) -> str:
    """Truncate text to *max_len* chars, appending '...' if cut."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def safe_message(text: str) -> str:
    """Ensure a message fits Telegram's limit."""
    return truncate(text, MAX_MSG_LEN)


# ---------------------------------------------------------------------------
# Section formatting
# ---------------------------------------------------------------------------


def section(title: str, body: str) -> str:
    """Bold title + body block."""
    return f"<b>{_escape_html(title)}</b>\n{body}"


def kv(key: str, value: Any) -> str:
    """Key-value line."""
    return f"<b>{_escape_html(str(key))}:</b> {_escape_html(_stringify(value))}"


def kv_block(pairs: Sequence[tuple[str, Any]]) -> str:
    """Multiple key-value lines."""
    return "\n".join(kv(k, v) for k, v in pairs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape_html(text: str) -> str:
    """Escape characters special in Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _stringify(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def no_data(label: str = "No data") -> str:
    return f"<i>{_escape_html(label)}</i>"
