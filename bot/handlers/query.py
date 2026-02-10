"""Advanced query handler (/q) -- guided builder + restricted raw SQL.

Uses aiogram FSM (finite state machine) for multi-step conversation flow.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import db
from bot.config import Config
from bot.queries import generic as gq
from bot.ui import formatters as fmt
from bot.ui.keyboards import back_keyboard

logger = logging.getLogger(__name__)

router = Router(name="query")


# ---------------------------------------------------------------------------
# FSM states
# ---------------------------------------------------------------------------


class QueryStates(StatesGroup):
    choose_mode = State()
    pick_table = State()
    pick_limit = State()
    enter_sql = State()


# ---------------------------------------------------------------------------
# Entry point: /q or callback
# ---------------------------------------------------------------------------


def _mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Guided builder", callback_data="q:guided"),
                InlineKeyboardButton(text="Raw SQL", callback_data="q:raw"),
            ],
            [back_keyboard().inline_keyboard[0][0]],
        ]
    )


@router.message(Command("q"))
async def cmd_query(message: Message, state: FSMContext) -> None:
    await state.set_state(QueryStates.choose_mode)
    await message.answer(
        fmt.section("Advanced Query", "Choose a mode:"),
        reply_markup=_mode_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(lambda cb: cb.data == "cmd:query")
async def cb_query_entry(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QueryStates.choose_mode)
    await callback.message.edit_text(
        fmt.section("Advanced Query", "Choose a mode:"),
        reply_markup=_mode_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Guided builder flow
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "q:guided", QueryStates.choose_mode)
async def cb_guided_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Step 1: pick a table."""
    try:
        tables = await gq.list_tables()
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return

    if not tables:
        await callback.message.edit_text(
            fmt.no_data("No tables found."),
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()
        return

    rows = [
        [InlineKeyboardButton(text=t, callback_data=f"q:tbl:{t}")]
        for t in tables[:20]  # safety cap
    ]
    rows.append([back_keyboard("cmd:query").inline_keyboard[0][0]])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await state.set_state(QueryStates.pick_table)
    await callback.message.edit_text(
        fmt.section("Guided Query", "Step 1: Pick a table"),
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("q:tbl:"), QueryStates.pick_table)
async def cb_guided_table(callback: CallbackQuery, state: FSMContext) -> None:
    """Step 2: pick a row limit."""
    table = callback.data.split(":", 2)[2]
    await state.update_data(table=table)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="10 rows", callback_data="q:lim:10"),
                InlineKeyboardButton(text="50 rows", callback_data="q:lim:50"),
                InlineKeyboardButton(text="100 rows", callback_data="q:lim:100"),
            ],
            [back_keyboard("cmd:query").inline_keyboard[0][0]],
        ]
    )

    await state.set_state(QueryStates.pick_limit)
    await callback.message.edit_text(
        fmt.section("Guided Query", f"Table: <code>{fmt._escape_html(table)}</code>\nStep 2: Pick row limit"),
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("q:lim:"), QueryStates.pick_limit)
async def cb_guided_limit(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    """Step 3: execute and display."""
    limit = int(callback.data.split(":")[2])
    data = await state.get_data()
    table = data.get("table", "")
    await state.clear()

    if not table or not gq._safe_identifier(table):
        await callback.answer("Invalid table.", show_alert=True)
        return

    try:
        headers, rows, total = await gq.browse_table(table, limit=limit, offset=0)
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return

    if not rows:
        await callback.message.edit_text(
            fmt.no_data(f"No rows in '{table}'."),
            reply_markup=back_keyboard("cmd:query"),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    table_out = fmt.mono_table(headers, rows)
    text = fmt.safe_message(
        fmt.section(
            f"Query Result: {table}",
            f"{len(rows)} row(s) of {total}\n{table_out}",
        )
    )
    await callback.message.edit_text(
        text, reply_markup=back_keyboard("cmd:query"), parse_mode="HTML"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Raw SQL mode
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "q:raw", QueryStates.choose_mode)
async def cb_raw_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QueryStates.enter_sql)
    await callback.message.edit_text(
        fmt.section(
            "Raw SQL",
            "Send a SELECT statement.\n"
            "Rules: SELECT only, no semicolons, max 100 rows.\n"
            "Send /cancel to abort.",
        ),
        reply_markup=back_keyboard("cmd:query"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Cancelled.", reply_markup=back_keyboard(), parse_mode="HTML")


@router.message(QueryStates.enter_sql)
async def msg_raw_sql(message: Message, state: FSMContext, config: Config) -> None:
    """Validate and execute a user-supplied SELECT."""
    sql = message.text.strip()
    await state.clear()

    # Validate
    error = gq.validate_select(sql)
    if error:
        await message.answer(
            fmt.section("Rejected", error),
            reply_markup=back_keyboard("cmd:query"),
            parse_mode="HTML",
        )
        return

    sql = gq.ensure_limit(sql, max_rows=100)

    try:
        rows = await db.execute_readonly(sql)
    except Exception as exc:
        logger.warning("Raw SQL error: %s", exc)
        await message.answer(
            fmt.section("SQL Error", fmt.truncate(str(exc), 300)),
            reply_markup=back_keyboard("cmd:query"),
            parse_mode="HTML",
        )
        return

    if not rows:
        await message.answer(
            fmt.no_data("Query returned no rows."),
            reply_markup=back_keyboard("cmd:query"),
            parse_mode="HTML",
        )
        return

    headers = list(rows[0].keys())
    data = [list(r.values()) for r in rows]
    table_out = fmt.mono_table(headers, data)
    text = fmt.safe_message(
        fmt.section("Query Result", f"{len(rows)} row(s)\n{table_out}")
    )
    await message.answer(text, reply_markup=back_keyboard("cmd:query"), parse_mode="HTML")
