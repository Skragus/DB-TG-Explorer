"""Weight handler (/weight) with trend and graph."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.queries import weight as wq
from bot.ui import formatters as fmt
from bot.ui.keyboards import (
    back_keyboard,
    paginated_keyboard,
    weight_actions,
)
from bot.utils import paging

router = Router(name="weight")

MODULE = "wt"


async def _weight_list(cfg: Config, offset: int = 0) -> tuple[str, ...]:
    """Return (text, module, offset, total) for the weight list view."""
    if not wq.available():
        return (fmt.no_data("Weight table not found."),)

    page = cfg.page_size
    rows = await wq.recent(limit=page, offset=offset)
    total = await wq.count()

    if not rows:
        return (fmt.no_data("No weight records."),)

    headers = [wq.date_col(), wq.value_col()]
    data = [[r.get(wq.date_col()), r.get(wq.value_col())] for r in rows]
    table = fmt.mono_table(headers, data)

    latest = rows[0]
    latest_val = latest.get(wq.value_col())
    latest_dt = latest.get(wq.date_col())
    header = fmt.kv("Latest", f"{latest_val} kg") if latest_val else ""
    text = fmt.safe_message(fmt.section("Weight", f"{header}\n\n{table}"))
    return text, offset, total


@router.message(Command("weight"))
async def cmd_weight(message: Message, config: Config) -> None:
    try:
        result = await _weight_list(config)
    except Exception:
        await message.answer("<i>DB unavailable.</i>", parse_mode="HTML")
        return
    if len(result) == 1:
        await message.answer(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total, extra_buttons=weight_actions())
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda cb: cb.data == "cmd:weight")
async def cb_weight(callback: CallbackQuery, config: Config) -> None:
    try:
        result = await _weight_list(config)
    except Exception:
        await callback.message.edit_text("<i>DB unavailable.</i>", parse_mode="HTML")
        await callback.answer()
        return
    if len(result) == 1:
        await callback.message.edit_text(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total, extra_buttons=weight_actions())
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# Pagination
@router.callback_query(F.data.startswith(f"p:{MODULE}:"))
async def cb_weight_page(callback: CallbackQuery, config: Config) -> None:
    _, offset, _ = paging.decode(callback.data)
    try:
        result = await _weight_list(config, offset)
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return
    if len(result) == 1:
        await callback.message.edit_text(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total, extra_buttons=weight_actions())
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# Trend
@router.callback_query(F.data == "wt:trend")
async def cb_weight_trend(callback: CallbackQuery, config: Config) -> None:
    try:
        recent_avg, prev_avg = await wq.trend_averages(7)
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return
    text = fmt.section(
        "Weight Trend (7d vs prev 7d)",
        fmt.trend_delta(recent_avg, prev_avg, "kg"),
    )
    await callback.message.edit_text(
        text, reply_markup=back_keyboard("cmd:weight"), parse_mode="HTML"
    )
    await callback.answer()


# Graph (sparkline)
@router.callback_query(F.data == "wt:graph")
async def cb_weight_graph(callback: CallbackQuery, config: Config) -> None:
    try:
        vals = await wq.sparkline_values(30)
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return
    if not vals:
        await callback.answer("No data for graph.", show_alert=True)
        return
    spark = fmt.sparkline(vals)
    nums = [v for v in vals if v is not None]
    lo = min(nums) if nums else 0
    hi = max(nums) if nums else 0
    text = fmt.section(
        "Weight (last 30)",
        f"<code>{spark}</code>\nRange: {lo:.1f} - {hi:.1f} kg",
    )
    await callback.message.edit_text(
        text, reply_markup=back_keyboard("cmd:weight"), parse_mode="HTML"
    )
    await callback.answer()
