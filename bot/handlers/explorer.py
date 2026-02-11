from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from bot import db
from bot.navigator import ExplorerCB, Paginator, build_breadcrumbs
from bot.config import Config

router = Router()

PAGE_SIZE = 10


@router.message(Command("start"))
async def cmd_start(message: Message, config: Config) -> None:
    """Show list of tables (Level 1)."""
    await show_tables(message, page=0)


async def show_tables(message: Message | CallbackQuery, page: int) -> None:
    """Render table list with pagination."""
    tables = await db.get_tables()
    paginator = Paginator(len(tables), page, PAGE_SIZE)
    
    current_tables = tables[paginator.offset : paginator.slice_end]
    
    kb = []
    for table in current_tables:
        kb.append([InlineKeyboardButton(
            text=f"📂 {table}",
            callback_data=ExplorerCB(action="table", table=table).pack()
        )])
        
    # Pagination controls
    nav_row = []
    if paginator.has_prev:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Prev",
            callback_data=ExplorerCB(action="list_tables", page=page - 1).pack()
        ))
    if paginator.has_next:
        nav_row.append(InlineKeyboardButton(
            text="Next ➡️",
            callback_data=ExplorerCB(action="list_tables", page=page + 1).pack()
        ))
    if nav_row:
        kb.append(nav_row)

    text = f"{build_breadcrumbs()}\n\nSelect a table to explore:"
    markup = InlineKeyboardMarkup(inline_keyboard=kb)

    if isinstance(message, Message):
        await message.answer(text, reply_markup=markup)
    else:
        await message.message.edit_text(text, reply_markup=markup)


@router.callback_query(ExplorerCB.filter(F.action == "list_tables"))
async def cb_list_tables(callback: CallbackQuery, callback_data: ExplorerCB) -> None:
    await show_tables(callback, callback_data.page)


@router.callback_query(ExplorerCB.filter(F.action == "table"))
async def cb_table_details(callback: CallbackQuery, callback_data: ExplorerCB) -> None:
    """Show table details (Columns + Browse Option) (Level 2)."""
    table = callback_data.table
    columns = await db.get_table_columns(table)
    row_count = await db.get_row_count(table)
    
    text = f"{build_breadcrumbs(table)}\n\n"
    text += f"📊 **Table:** `{table}`\n"
    text += f"🔢 **Rows:** {row_count}\n\n"
    text += "**Columns:**\n"
    
    for col in columns[:10]:  # Show first 10 columns only in summary
        pk_mark = "" # TODO: Identify PK
        text += f"- `{col['name']}` ({col['type']})\n"
        
    if len(columns) > 10:
        text += f"... and {len(columns) - 10} more.\n"

    kb = [
        [InlineKeyboardButton(
            text="🔍 Browse Rows",
            callback_data=ExplorerCB(action="rows", table=table, page=0).pack()
        )],
        [InlineKeyboardButton(
            text="⬅️ Back to Tables",
            callback_data=ExplorerCB(action="list_tables", page=0).pack()
        )]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(ExplorerCB.filter(F.action == "rows"))
async def cb_browse_rows(callback: CallbackQuery, callback_data: ExplorerCB) -> None:
    """Show paginated rows (Level 3)."""
    table = callback_data.table
    page = callback_data.page
    
    # We need a stable sort to paginate correctly. 
    # Attempt to find PK or default to first column.
    pk_cols = await db.get_primary_key(table)
    sort_col = pk_cols[0] if pk_cols else None
    
    rows = await db.get_rows(table, limit=PAGE_SIZE, offset=page * PAGE_SIZE, sort_by=sort_col)
    total_rows = await db.get_row_count(table)
    paginator = Paginator(total_rows, page, PAGE_SIZE)

    text = f"{build_breadcrumbs(table)}\n\nBrowse rows ({paginator.offset + 1}-{paginator.slice_end} of {total_rows}):"
    
    kb = []
    for row in rows:
        # Try to find a good label for the button
        # If PK exists, use it. Else use first column.
        label_col = sort_col if sort_col else (list(row.keys())[0] if row.keys() else "Row")
        val = str(row[label_col])
        if len(val) > 30: val = val[:27] + "..."
        
        # We need a way to identify the row. 
        # For now, we only support tables with single-column PKs cleanly.
        # If no PK, we might struggle to "select" a row reliably.
        # But let's use the `sort_col` value as the identifier if available.
        
        btn_text = f"{label_col}: {val}"
        
        # Only add click handler if we have a way to identify the row (PK)
        if pk_cols and len(pk_cols) == 1:
            pk_val = str(row[pk_cols[0]])
            kb.append([InlineKeyboardButton(
                text=btn_text,
                callback_data=ExplorerCB(action="row_detail", table=table, pk_val=pk_val).pack()
            )])
        else:
            # Read-only list item if no single PK
            kb.append([InlineKeyboardButton(text=btn_text, callback_data="noop")])

    # Pagiation
    nav_row = []
    if paginator.has_prev:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=ExplorerCB(action="rows", table=table, page=page-1).pack()))
    
    nav_row.append(InlineKeyboardButton(text="⬆️ Up", callback_data=ExplorerCB(action="table", table=table).pack()))
    
    if paginator.has_next:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=ExplorerCB(action="rows", table=table, page=page+1).pack()))
        
    kb.append(nav_row)

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(ExplorerCB.filter(F.action == "row_detail"))
async def cb_row_detail(callback: CallbackQuery, callback_data: ExplorerCB) -> None:
    """Show single row details."""
    table = callback_data.table
    pk_val = callback_data.pk_val
    
    pk_cols = await db.get_primary_key(table)
    if not pk_cols:
        await callback.answer("No primary key defined", show_alert=True)
        return
        
    # Assuming single PK dependent on int/str inference
    # We cast to int if it looks like one, else str.
    # ideally introspection would tell us type.
    try:
        val = int(pk_val)
    except ValueError:
        val = pk_val
        
    row = await db.get_row_by_pk(table, pk_cols[0], val)
    
    if not row:
        await callback.answer("Row not found", show_alert=True)
        return
        
    text = f"{build_breadcrumbs(table, pk_val)}\n\n"
    for k, v in row.items():
        text += f"**{k}**: `{v}`\n"
        
    kb = [[InlineKeyboardButton(
        text="⬅️ Back to Rows",
        callback_data=ExplorerCB(action="rows", table=table, page=0).pack()  # TODO: Remember page?
    )]]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
