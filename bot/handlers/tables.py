"""Tables explorer handler (/tables, /describe)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.queries import generic as gq
from bot.ui import formatters as fmt
from bot.ui.keyboards import (
    back_keyboard,
    drill_down,
    paginated_keyboard,
    table_actions,
)
from bot.utils import paging

router = Router(name="tables")


# ---------------------------------------------------------------------------
# /tables -- list public tables
# ---------------------------------------------------------------------------


async def _tables_text() -> tuple[str, list[tuple[str, str]]]:
    tables = await gq.list_tables()
    if not tables:
        return fmt.no_data("No tables in public schema."), []

    items = [(t, f"tbl:pick:{t}") for t in tables]
    text = fmt.section("Tables", f"{len(tables)} table(s) in public schema")
    return text, items


@router.message(Command("tables"))
async def cmd_tables(message: Message) -> None:
    try:
        text, items = await _tables_text()
    except Exception:
        await message.answer("<i>DB unavailable.</i>", parse_mode="HTML")
        return
    kb = drill_down(items) if items else back_keyboard()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda cb: cb.data == "cmd:tables")
async def cb_tables(callback: CallbackQuery) -> None:
    try:
        text, items = await _tables_text()
    except Exception:
        await callback.message.edit_text("<i>DB unavailable.</i>", parse_mode="HTML")
        await callback.answer()
        return
    kb = drill_down(items) if items else back_keyboard()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ---------------------------------------------------------------------------
# Pick a table -> show Describe / Browse buttons
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith("tbl:pick:"))
async def cb_table_pick(callback: CallbackQuery) -> None:
    table = callback.data.split(":", 2)[2]
    text = fmt.section("Table", f"<code>{fmt._escape_html(table)}</code>")
    from aiogram.types import InlineKeyboardMarkup

    rows = table_actions(table)
    rows.append([back_keyboard("cmd:tables").inline_keyboard[0][0]])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ---------------------------------------------------------------------------
# /describe <table>
# ---------------------------------------------------------------------------


async def _describe_text(table: str) -> str:
    columns, indexes = await gq.describe_table(table)
    if not columns:
        return fmt.no_data(f"Table '{table}' not found or has no columns.")

    headers = ["Column", "Type", "Null?"]
    rows = [[c["name"], c["type"], c["nullable"]] for c in columns]
    body = fmt.mono_table(headers, rows)

    idx_text = ""
    if indexes:
        idx_lines = [f"  {ix['name']}" for ix in indexes]
        idx_text = "\n\n<b>Indexes:</b>\n" + "\n".join(idx_lines)

    return fmt.safe_message(
        fmt.section(f"Table: {table}", f"{len(columns)} columns\n{body}{idx_text}")
    )


@router.message(Command("describe"))
async def cmd_describe(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Usage: /describe &lt;table_name&gt;",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )
        return
    table = parts[1].strip()
    try:
        text = await _describe_text(table)
    except Exception:
        text = "<i>DB unavailable.</i>"
    await message.answer(text, reply_markup=back_keyboard("cmd:tables"), parse_mode="HTML")


@router.callback_query(F.data.startswith("tbl:desc:"))
async def cb_describe(callback: CallbackQuery) -> None:
    table = callback.data.split(":", 2)[2]
    try:
        text = await _describe_text(table)
    except Exception:
        text = "<i>DB unavailable.</i>"
    await callback.message.edit_text(
        text, reply_markup=back_keyboard("cmd:tables"), parse_mode="HTML"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Browse table rows (paginated)
# ---------------------------------------------------------------------------

BROWSE_MODULE = "brw"


async def _browse_text(table: str, cfg: Config, offset: int = 0) -> tuple[str, int, int | None]:
    page = cfg.browse_page_size
    headers, rows, total = await gq.browse_table(table, limit=page, offset=offset)
    if not rows:
        return fmt.no_data(f"No rows in '{table}'."), offset, total

    table_out = fmt.mono_table(headers, rows)
    text = fmt.safe_message(
        fmt.section(f"Browse: {table}", f"Rows {offset+1}-{offset+len(rows)}\n{table_out}")
    )
    return text, offset, total


@router.callback_query(F.data.startswith(f"p:{BROWSE_MODULE}:"))
async def cb_browse(callback: CallbackQuery, config: Config) -> None:
    _, offset, table = paging.decode(callback.data)
    if not table:
        await callback.answer("Missing table name.", show_alert=True)
        return
    try:
        text, off, total = await _browse_text(table, config, offset)
    except Exception:
        await callback.answer("DB error", show_alert=True)
        return
    kb = paginated_keyboard(
        BROWSE_MODULE, off, config.browse_page_size, total, extra=table
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
