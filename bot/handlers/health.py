"""Bot health / status handler (/health)."""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot import db
from bot.config import Config
from bot.ui.formatters import kv_block, section
from bot.ui.keyboards import back_keyboard
from bot.utils.time import format_dt

router = Router(name="health")


def _build_health_text(cfg: Config, db_ok: bool) -> str:
    now = datetime.now(timezone.utc)
    uptime = now - cfg.bot_started_at
    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    mins, secs = divmod(rem, 60)

    last_q = db.last_successful_query
    last_q_str = format_dt(last_q, cfg.tz) if last_q else "never"

    pairs = [
        ("Uptime", f"{hours}h {mins}m {secs}s"),
        ("DB status", "OK" if db_ok else "UNREACHABLE"),
        ("Last query", last_q_str),
        ("Timezone", str(cfg.tz)),
    ]
    return section("Bot Health", kv_block(pairs))


@router.message(Command("health"))
async def cmd_health(message: Message, config: Config) -> None:
    db_ok = await db.health_check()
    await message.answer(
        _build_health_text(config, db_ok),
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(lambda cb: cb.data == "cmd:health")
async def cb_health(callback: CallbackQuery, config: Config) -> None:
    db_ok = await db.health_check()
    await callback.message.edit_text(
        _build_health_text(config, db_ok),
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
