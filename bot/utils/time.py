"""Timezone-aware time helpers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def now_local(tz: ZoneInfo) -> datetime:
    """Current wall-clock time in *tz*."""
    return datetime.now(timezone.utc).astimezone(tz)


def today_local(tz: ZoneInfo) -> date:
    """Today's date in *tz*."""
    return now_local(tz).date()


def today_range_utc(tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Return (start, end) of 'today' in *tz*, expressed as UTC datetimes.

    Useful for WHERE clauses on UTC-stored timestamps.
    """
    local_today = today_local(tz)
    start_local = datetime.combine(local_today, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def day_range_utc(d: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Return (start, end) of a specific *date* in *tz*, as UTC."""
    start_local = datetime.combine(d, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def n_days_ago_utc(n: int, tz: ZoneInfo) -> datetime:
    """Return UTC timestamp for midnight *n* days ago in *tz*."""
    d = today_local(tz) - timedelta(days=n)
    return datetime.combine(d, time.min, tzinfo=tz).astimezone(timezone.utc)


def format_dt(dt: datetime, tz: ZoneInfo) -> str:
    """Format a datetime as ``YYYY-MM-DD HH:MM`` in *tz*."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def format_date(d: date) -> str:
    """Format a date as ``YYYY-MM-DD``."""
    return d.isoformat()


def format_duration(minutes: float | None) -> str:
    """Format duration in minutes to ``Xh Ym`` string."""
    if minutes is None:
        return "N/A"
    h = int(minutes) // 60
    m = int(minutes) % 60
    if h:
        return f"{h}h {m}m"
    return f"{m}m"
