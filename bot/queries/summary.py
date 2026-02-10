"""Cross-domain summary aggregation for today / week / month views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bot.queries import heart, sleep, steps, weight
from bot.utils.time import n_days_ago_utc, today_range_utc


@dataclass
class TodaySummary:
    weight_latest: dict[str, Any] | None = None
    steps_today: int | None = None
    sleep_last: dict[str, Any] | None = None
    heart_summary: dict[str, Any] | None = None


async def get_today(tz: ZoneInfo) -> TodaySummary:
    """Gather today's snapshot across all domains."""
    start, end = today_range_utc(tz)
    s = TodaySummary()
    if weight.available():
        s.weight_latest = await weight.latest()
    if steps.available():
        s.steps_today = await steps.today_steps(start, end)
    if sleep.available():
        s.sleep_last = await sleep.last_night(start, end)
    if heart.available():
        s.heart_summary = await heart.today_summary(start, end)
    return s


@dataclass
class PeriodSummary:
    days: int = 0
    weight_first: float | None = None
    weight_last: float | None = None
    weight_delta: float | None = None
    steps_avg: float | None = None
    steps_total: int | None = None
    sleep_avg_duration: float | None = None


async def get_period(days: int, tz: ZoneInfo) -> PeriodSummary:
    """Aggregate summary for the last *days* days."""
    start = n_days_ago_utc(days, tz)
    now_start, now_end = today_range_utc(tz)
    s = PeriodSummary(days=days)

    if weight.available():
        rows = await weight.in_range(start, now_end)
        if rows:
            vals = [r[weight.value_col()] for r in rows if r.get(weight.value_col()) is not None]
            if vals:
                s.weight_first = float(vals[0])
                s.weight_last = float(vals[-1])
                s.weight_delta = s.weight_last - s.weight_first

    if steps.available():
        s.steps_avg = await steps.avg_steps(days, start)
        s.steps_total = await steps.total_steps(start)

    if sleep.available():
        s.sleep_avg_duration = await sleep.avg_duration(start)

    return s
