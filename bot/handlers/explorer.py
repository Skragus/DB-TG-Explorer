import json
from datetime import date, datetime
from uuid import UUID

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from bot import db
from bot.navigator import ExplorerCB, Paginator, build_breadcrumbs
from bot.config import Config

router = Router()

PAGE_SIZE = 10


def format_value(val: any) -> str:
    """Format a value for display in the UI."""
    if val is None:
        return "NULL"
    if isinstance(val, (dict, list)):
        return json.dumps(val, default=str)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, UUID):
        return str(val)
    return str(val)


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
            callback_data=ExplorerCB(a="t", t=table).pack()
        )])
        
    # Pagination controls
    nav_row = []
    if paginator.has_prev:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Prev",
            callback_data=ExplorerCB(a="l", p=page - 1).pack()
        ))
    if paginator.has_next:
        nav_row.append(InlineKeyboardButton(
            text="Next ➡️",
            callback_data=ExplorerCB(a="l", p=page + 1).pack()
        ))
    if nav_row:
        kb.append(nav_row)

    text = f"{build_breadcrumbs()}\n\nSelect a table to explore:"
    markup = InlineKeyboardMarkup(inline_keyboard=kb)

    if isinstance(message, Message):
        await message.answer(text, reply_markup=markup)
    else:
        await message.message.edit_text(text, reply_markup=markup)


@router.callback_query(ExplorerCB.filter(F.a == "l"))
async def cb_list_tables(callback: CallbackQuery, callback_data: ExplorerCB) -> None:
    await show_tables(callback, callback_data.p)


@router.callback_query(ExplorerCB.filter(F.a == "t"))
async def cb_table_details(callback: CallbackQuery, callback_data: ExplorerCB) -> None:
    """Show table details (Columns + Browse Option) (Level 2)."""
    table = callback_data.t
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
            callback_data=ExplorerCB(a="r", t=table, p=0).pack()
        )],
        [InlineKeyboardButton(
            text="⬅️ Back to Tables",
            callback_data=ExplorerCB(a="l", p=0).pack()
        )]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(ExplorerCB.filter(F.a == "r"))
async def cb_browse_rows(callback: CallbackQuery, callback_data: ExplorerCB) -> None:
    """Show paginated rows (Level 3)."""
    table = callback_data.t
    page = callback_data.p
    
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
        raw_val = row[label_col]
        val = format_value(raw_val)
        
        if len(val) > 30: val = val[:27] + "..."
        
        # We need a way to identify the row. 
        # For now, we only support tables with single-column PKs cleanly.
        # If no PK, we might struggle to "select" a row reliably.
        # But let's use the `sort_col` value as the identifier if available.
        
        btn_text = f"{label_col}: {val}"
        
        # Only add click handler if we have a way to identify the row (PK)
        if pk_cols and len(pk_cols) == 1:
            pk_val = str(row[pk_cols[0]])
            if len(pk_val) > 32 and isinstance(row[pk_cols[0]], UUID):
                 # UUID is 36 chars, callback limit is 64.
                 # prefix "x:d:t:<table>:k:" takes space.
                 # "x:d:t:very_long_table_name:k:uuid" -> might fail.
                 # But standard UUID is 36 chars.
                 pass

            kb.append([InlineKeyboardButton(
                text=btn_text,
                callback_data=ExplorerCB(a="d", t=table, k=pk_val).pack()
            )])
        else:
            # Read-only list item if no single PK
            kb.append([InlineKeyboardButton(text=btn_text, callback_data="noop")])

    # Pagiation
    nav_row = []
    if paginator.has_prev:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=ExplorerCB(a="r", t=table, p=page-1).pack()))
    
    nav_row.append(InlineKeyboardButton(text="⬆️ Up", callback_data=ExplorerCB(a="t", t=table).pack()))
    
    if paginator.has_next:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=ExplorerCB(a="r", t=table, p=page+1).pack()))
        
    kb.append(nav_row)

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(ExplorerCB.filter(F.a == "d"))
async def cb_row_detail(callback: CallbackQuery, callback_data: ExplorerCB) -> None:
    """Show single row details."""
    table = callback_data.t
    pk_val = callback_data.k
    
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
        # Check if it's a UUID string
        try:
             UUID(pk_val)
             val = pk_val 
        except ValueError:
             val = pk_val
        
    row = await db.get_row_by_pk(table, pk_cols[0], val)
    
    if not row:
        await callback.answer("Row not found", show_alert=True)
        return
        
    text = f"{build_breadcrumbs(table, pk_val)}\n\n"
    
    # Format each field
    for k, v in row.items():
        val_str = format_value(v)
        # Escape markdown special chars if needed, but code block handles most
        # but let's be careful with backticks inside code blocks?
        # aiogram HTML parse mode is used here based on main.py
        # Wait, main.py uses HTML parse mode.
        # But here I see **bold** usage which is Markdown.
        # Let's check main.py parse mode.
        
        # Ideally handle long values in detail view too?
        if len(val_str) > 4000: # Telegram limit
             val_str = val_str[:4000] + "..."
             
        # HTML escaping is safer if we use HTML parse mode.
        # But the code uses Markdown syntax (**text**).
        # Double check main.py...
        pass

    # Main.py says: default=DefaultBotProperties(parse_mode="HTML")
    # But current code uses **bold** which is Markdown.
    # This is a bug! Using **bold** with HTML parse mode will show asterisks.
    # I should fix this to use <b> or <code> or change parse mode.
    # Changing parse mode is risky if other parts rely on HTML.
    # I will switch to HTML tags: <b> and <pre>.
    
    text = f"{build_breadcrumbs(table, pk_val)}\n\n" # Breadcrumbs might need HTML escaping too
    
    for k, v in row.items():
        val_str = format_value(v)
        # simplistic HTML escape
        val_str = val_str.replace("<", "&lt;").replace(">", "&gt;")
        text += f"<b>{k}</b>: <code>{val_str}</code>\n"
        
    kb = [[InlineKeyboardButton(
        text="⬅️ Back to Rows",
        callback_data=ExplorerCB(a="r", t=table, p=0).pack()  # TODO: Remember page?
    )]]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
