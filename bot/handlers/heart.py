"""Heart rate handler (/heart) with graph."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message

from bot.config import Config
from bot.queries import heart as hq
from bot.ui import formatters as fmt
from bot.ui.keyboards import back_keyboard, paginated_keyboard
from bot.utils import paging

router = Router(name="heart")

MODULE = "hr"


def _heart_actions() -> list[list[InlineKeyboardButton]]:
    return [
        [InlineKeyboardButton(text="Graph", callback_data="hr:graph")]
    ]


async def _heart_list(cfg: Config, offset: int = 0) -> tuple[str, ...]:
    if not hq.available():
        return (fmt.no_data("Heart rate table not found."),)

    page = cfg.page_size
    rows = await hq.recent(limit=page, offset=offset)
    total = await hq.count()
    if not rows:
        return (fmt.no_data("No heart rate records."),)

    headers = [hq.date_col(), hq.value_col()]
    data = [[r.get(hq.date_col()), r.get(hq.value_col())] for r in rows]
    table = fmt.mono_table(headers, data)

    latest = rows[0]
    latest_val = latest.get(hq.value_col())
    header = fmt.kv("Latest", f"{latest_val} bpm") if latest_val else ""

    text = fmt.safe_message(fmt.section("Heart Rate", f"{header}\n\n{table}"))
    return text, offset, total


@router.message(Command("heart"))
async def cmd_heart(message: Message, config: Config) -> None:
    try:
        result = await _heart_list(config)
    except Exception:
        await message.answer("<i>DB unavailable.</i>", parse_mode="HTML")
        return
    if len(result) == 1:
        await message.answer(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total, extra_buttons=_heart_actions())
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda cb: cb.data == "cmd:heart")
async def cb_heart(callback: CallbackQuery, config: Config) -> None:
    try:
        result = await _heart_list(config)
    except Exception:
        await callback.message.edit_text("<i>DB unavailable.</i>", parse_mode="HTML")
        await callback.answer()
        return
    if len(result) == 1:
        await callback.message.edit_text(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total, extra_buttons=_heart_actions())
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# Pagination
@router.callback_query(F.data.startswith(f"p:{MODULE}:"))
async def cb_heart_page(callback: CallbackQuery, config: Config) -> None:
    _, offset, _ = paging.decode(callback.data)
    try:
        result = await _heart_list(config, offset)
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return
    if len(result) == 1:
        await callback.message.edit_text(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total, extra_buttons=_heart_actions())
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# Graph
@router.callback_query(F.data == "hr:graph")
async def cb_heart_graph(callback: CallbackQuery, config: Config) -> None:
    try:
        vals = await hq.sparkline_values(30)
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
        "Heart Rate (last 30)",
        f"<code>{spark}</code>\nRange: {lo} - {hi} bpm",
    )
    await callback.message.edit_text(
        text, reply_markup=back_keyboard("cmd:heart"), parse_mode="HTML"
    )
    await callback.answer()
