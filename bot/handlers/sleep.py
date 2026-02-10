"""Sleep handler (/sleep) showing recent sessions."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.queries import sleep as slq
from bot.ui import formatters as fmt
from bot.ui.keyboards import back_keyboard, paginated_keyboard
from bot.utils import paging
from bot.utils.time import format_dt, format_duration

router = Router(name="sleep")

MODULE = "sl"


def _format_session(row: dict, cfg: Config) -> str:
    """Format a single sleep session as a text block."""
    parts: list[str] = []

    start = row.get(slq.start_col()) if slq.start_col() else None
    end = row.get(slq.end_col()) if slq.end_col() else None
    dur = row.get(slq.duration_col()) if slq.duration_col() else None

    date_str = ""
    if start:
        date_str = format_dt(start, cfg.tz)
    time_range = ""
    if start and end:
        time_range = f"{format_dt(start, cfg.tz)} - {format_dt(end, cfg.tz)}"

    if date_str:
        parts.append(f"  {date_str}")
    if time_range:
        parts.append(f"  {time_range}")
    if dur is not None:
        parts.append(f"  Duration: {format_duration(dur)}")

    # Stages breakdown if available
    stages = row.get(slq.stages_col()) if slq.stages_col() else None
    if stages:
        if isinstance(stages, dict):
            stage_parts = [f"{k}: {v}" for k, v in stages.items()]
            parts.append(f"  Stages: {', '.join(stage_parts)}")
        else:
            parts.append(f"  Stages: {fmt.truncate(str(stages), 120)}")

    return "\n".join(parts)


async def _sleep_list(cfg: Config, offset: int = 0) -> tuple[str, ...]:
    if not slq.available():
        return (fmt.no_data("Sleep table not found."),)

    page = cfg.page_size
    rows = await slq.recent(limit=page, offset=offset)
    total = await slq.count()
    if not rows:
        return (fmt.no_data("No sleep records."),)

    blocks = [_format_session(r, cfg) for r in rows]
    body = "\n\n".join(blocks)
    text = fmt.safe_message(fmt.section("Sleep Sessions", body))
    return text, offset, total


@router.message(Command("sleep"))
async def cmd_sleep(message: Message, config: Config) -> None:
    try:
        result = await _sleep_list(config)
    except Exception:
        await message.answer("<i>DB unavailable.</i>", parse_mode="HTML")
        return
    if len(result) == 1:
        await message.answer(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda cb: cb.data == "cmd:sleep")
async def cb_sleep(callback: CallbackQuery, config: Config) -> None:
    try:
        result = await _sleep_list(config)
    except Exception:
        await callback.message.edit_text("<i>DB unavailable.</i>", parse_mode="HTML")
        await callback.answer()
        return
    if len(result) == 1:
        await callback.message.edit_text(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# Pagination
@router.callback_query(F.data.startswith(f"p:{MODULE}:"))
async def cb_sleep_page(callback: CallbackQuery, config: Config) -> None:
    _, offset, _ = paging.decode(callback.data)
    try:
        result = await _sleep_list(config, offset)
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return
    if len(result) == 1:
        await callback.message.edit_text(result[0], reply_markup=back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text, offset, total = result
    kb = paginated_keyboard(MODULE, offset, config.page_size, total)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
