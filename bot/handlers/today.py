"""Today's summary handler (/today)."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.queries.summary import get_today
from bot.ui.formatters import kv, no_data, section, safe_message
from bot.ui.keyboards import back_keyboard
from bot.utils.time import format_dt, format_duration
from bot.queries import weight as wq, steps as sq, sleep as slq, heart as hq

router = Router(name="today")


async def _build_today(cfg: Config) -> str:
    s = await get_today(cfg.tz)
    lines: list[str] = []

    # Weight
    if wq.available():
        if s.weight_latest:
            val = s.weight_latest.get(wq.value_col())
            dt = s.weight_latest.get(wq.date_col())
            dt_str = format_dt(dt, cfg.tz) if dt else ""
            lines.append(kv("Weight", f"{val} kg  ({dt_str})"))
        else:
            lines.append(kv("Weight", "no record today"))
    else:
        lines.append(kv("Weight", "table not found"))

    # Steps
    if sq.available():
        if s.steps_today is not None:
            lines.append(kv("Steps", f"{s.steps_today:,}"))
        else:
            lines.append(kv("Steps", "no record today"))
    else:
        lines.append(kv("Steps", "table not found"))

    # Sleep
    if slq.available():
        if s.sleep_last:
            dur = s.sleep_last.get(slq.duration_col()) if slq.duration_col() else None
            dur_str = format_duration(dur) if dur is not None else "N/A"
            start = s.sleep_last.get(slq.start_col()) if slq.start_col() else None
            end = s.sleep_last.get(slq.end_col()) if slq.end_col() else None
            time_str = ""
            if start and end:
                time_str = f"  ({format_dt(start, cfg.tz)} - {format_dt(end, cfg.tz)})"
            lines.append(kv("Sleep", f"{dur_str}{time_str}"))
        else:
            lines.append(kv("Sleep", "no record last night"))
    else:
        lines.append(kv("Sleep", "table not found"))

    # Heart
    if hq.available():
        if s.heart_summary:
            avg = s.heart_summary.get("avg_bpm")
            lo = s.heart_summary.get("min_bpm")
            hi = s.heart_summary.get("max_bpm")
            n = s.heart_summary.get("samples", 0)
            avg_str = f"{avg:.0f}" if avg else "?"
            lines.append(kv("Heart", f"avg {avg_str} bpm  (lo {lo}, hi {hi}, {n} samples)"))
        else:
            lines.append(kv("Heart", "no record today"))
    else:
        lines.append(kv("Heart", "table not found"))

    body = "\n".join(lines) if lines else no_data()
    return safe_message(section("Today's Summary", body))


@router.message(Command("today"))
async def cmd_today(message: Message, config: Config) -> None:
    try:
        text = await _build_today(config)
    except Exception:
        text = "<i>DB unavailable - try again later.</i>"
    await message.answer(text, reply_markup=back_keyboard(), parse_mode="HTML")


@router.callback_query(lambda cb: cb.data == "cmd:today")
async def cb_today(callback: CallbackQuery, config: Config) -> None:
    try:
        text = await _build_today(config)
    except Exception:
        text = "<i>DB unavailable - try again later.</i>"
    await callback.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="HTML")
    await callback.answer()
