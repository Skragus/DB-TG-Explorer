"""Steps handler (/steps) with averages and graph."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.queries import steps as sq
from bot.ui import formatters as fmt
from bot.ui.keyboards import (
    back_keyboard,
    paginated_keyboard,
    steps_actions,
)
from bot.utils import paging
from bot.utils.time import n_days_ago_utc

router = Router(name="steps")

MODULE = "st"


async def _steps_list(cfg: Config, offset: int = 0) -> tuple[str, ...]:
    if not sq.available():
        return (fmt.no_data("Steps table not found."),)

    page = cfg.page_size
    rows = await sq.recent(limit=page, offset=offset)
    total = await sq.count()
    if not rows:
        return (fmt.no_data("No step records."),)

    headers = [sq.date_col(), sq.value_col()]
    data = [[r.get(sq.date_col()), r.get(sq.value_col())] for r in rows]
    table = fmt.mono_table(headers, data)

    # Averages
    avg7_start = n_days_ago_utc(7, cfg.tz)
    avg30_start = n_days_ago_utc(30, cfg.tz)
    avg7 = await sq.avg_steps(7, avg7_start)
    avg30 = await sq.avg_steps(30, avg30_start)

    avg_line = ""
    if avg7 is not None:
        avg_line += fmt.kv("7d avg", f"{avg7:,.0f}")
    if avg30 is not None:
        avg_line += "\n" + fmt.kv("30d avg", f"{avg30:,.0f}")

    text = fmt.safe_message(fmt.section("Steps", f"{avg_line}\n\n{table}"))
    return text, offset, total


@router.message(Command("steps"))
async def cmd_steps(message: Message, config: Config) -> None:
    try:
        result = await _steps_list(config)
    except Exception:
        await message.answer("<i>DB unavailable.</i>", parse_mode="HTML")
        return
    if len(result) == 1:
        await message.answer(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total, extra_buttons=steps_actions())
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda cb: cb.data == "cmd:steps")
async def cb_steps(callback: CallbackQuery, config: Config) -> None:
    try:
        result = await _steps_list(config)
    except Exception:
        await callback.message.edit_text("<i>DB unavailable.</i>", parse_mode="HTML")
        await callback.answer()
        return
    if len(result) == 1:
        await callback.message.edit_text(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total, extra_buttons=steps_actions())
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# Pagination
@router.callback_query(F.data.startswith(f"p:{MODULE}:"))
async def cb_steps_page(callback: CallbackQuery, config: Config) -> None:
    _, offset, _ = paging.decode(callback.data)
    try:
        result = await _steps_list(config, offset)
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return
    if len(result) == 1:
        await callback.message.edit_text(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total, extra_buttons=steps_actions())
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# Graph
@router.callback_query(F.data == "st:graph")
async def cb_steps_graph(callback: CallbackQuery, config: Config) -> None:
    try:
        vals = await sq.sparkline_values(30)
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return
    if not vals:
        await callback.answer("No data for graph.", show_alert=True)
        return
    spark = fmt.sparkline(vals)
    nums = [v for v in vals if v is not None]
    lo = int(min(nums)) if nums else 0
    hi = int(max(nums)) if nums else 0
    text = fmt.section(
        "Steps (last 30 days)",
        f"<code>{spark}</code>\nRange: {lo:,} - {hi:,}",
    )
    await callback.message.edit_text(
        text, reply_markup=back_keyboard("cmd:steps"), parse_mode="HTML"
    )
    await callback.answer()
