"""Home menu handler (/start)."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.ui.keyboards import home_menu

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "<b>DB Explorer</b>\nChoose a section:",
        reply_markup=home_menu(),
        parse_mode="HTML",
    )


@router.callback_query(lambda cb: cb.data == "cmd:start")
async def cb_start(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "<b>DB Explorer</b>\nChoose a section:",
        reply_markup=home_menu(),
        parse_mode="HTML",
    )
    await callback.answer()
