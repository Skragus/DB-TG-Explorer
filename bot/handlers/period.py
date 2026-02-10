"""Week / month summary handlers (/week, /month) with drill-down."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.queries.summary import get_period
from bot.ui.formatters import kv, kv_block, no_data, safe_message, section, trend_delta
from bot.ui.keyboards import back_keyboard, period_drill
from bot.utils.time import format_duration

from aiogram.types import InlineKeyboardMarkup

router = Router(name="period")


async def _build_period(days: int, cfg: Config) -> tuple[str, InlineKeyboardMarkup]:
    s = await get_period(days, cfg.tz)
    label = f"Last {days} days"
    pairs: list[tuple[str, str]] = []

    if s.weight_delta is not None:
        sign = "+" if s.weight_delta >= 0 else ""
        pairs.append(("Weight change", f"{sign}{s.weight_delta:.1f} kg  ({s.weight_first:.1f} -> {s.weight_last:.1f})"))
    else:
        pairs.append(("Weight change", "N/A"))

    if s.steps_avg is not None:
        pairs.append(("Steps avg/day", f"{s.steps_avg:,.0f}"))
    else:
        pairs.append(("Steps avg/day", "N/A"))

    if s.steps_total is not None:
        pairs.append(("Steps total", f"{s.steps_total:,}"))
    else:
        pairs.append(("Steps total", "N/A"))

    if s.sleep_avg_duration is not None:
        pairs.append(("Sleep avg", format_duration(s.sleep_avg_duration)))
    else:
        pairs.append(("Sleep avg", "N/A"))

    text = safe_message(section(label, kv_block(pairs)))
    period_key = "week" if days <= 7 else "month"
    kb = InlineKeyboardMarkup(
        inline_keyboard=period_drill(period_key) + [[back_keyboard().inline_keyboard[0][0]]]
    )
    return text, kb


# --- /week ---

@router.message(Command("week"))
async def cmd_week(message: Message, config: Config) -> None:
    try:
        text, kb = await _build_period(7, config)
    except Exception:
        text, kb = "<i>DB unavailable.</i>", back_keyboard()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda cb: cb.data == "cmd:week")
async def cb_week(callback: CallbackQuery, config: Config) -> None:
    try:
        text, kb = await _build_period(7, config)
    except Exception:
        text, kb = "<i>DB unavailable.</i>", back_keyboard()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# --- /month ---

@router.message(Command("month"))
async def cmd_month(message: Message, config: Config) -> None:
    try:
        text, kb = await _build_period(30, config)
    except Exception:
        text, kb = "<i>DB unavailable.</i>", back_keyboard()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda cb: cb.data == "cmd:month")
async def cb_month(callback: CallbackQuery, config: Config) -> None:
    try:
        text, kb = await _build_period(30, config)
    except Exception:
        text, kb = "<i>DB unavailable.</i>", back_keyboard()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# --- Drill-down: daily rows ---

@router.callback_query(F.data.startswith("drill:"))
async def cb_drill(callback: CallbackQuery, config: Config) -> None:
    """Show daily detail rows for the period."""
    parts = callback.data.split(":")
    period = parts[1] if len(parts) > 1 else "week"
    offset = int(parts[2]) if len(parts) > 2 else 0
    days = 7 if period == "week" else 30

    from bot.queries import weight as wq, steps as sq
    from bot.utils.time import n_days_ago_utc, today_range_utc
    from bot.ui.formatters import mono_table

    start = n_days_ago_utc(days, config.tz)
    _, end = today_range_utc(config.tz)

    lines: list[str] = []

    # Weight rows
    if wq.available():
        rows = await wq.in_range(start, end)
        if rows:
            headers = [wq.date_col(), wq.value_col()]
            data = [[r.get(wq.date_col()), r.get(wq.value_col())] for r in rows]
            lines.append(f"<b>Weight ({len(data)} rows)</b>\n" + mono_table(headers, data))

    # Steps rows
    if sq.available():
        rows = await sq.in_range(start, end)
        if rows:
            headers = [sq.date_col(), sq.value_col()]
            data = [[r.get(sq.date_col()), r.get(sq.value_col())] for r in rows]
            lines.append(f"<b>Steps ({len(data)} rows)</b>\n" + mono_table(headers, data))

    text = "\n\n".join(lines) if lines else no_data("No daily rows found.")
    from bot.ui.formatters import safe_message
    text = safe_message(text)

    parent_cb = f"cmd:{period}"
    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(parent_cb),
        parse_mode="HTML",
    )
    await callback.answer()
