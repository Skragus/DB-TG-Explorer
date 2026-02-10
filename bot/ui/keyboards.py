"""Inline keyboard factories for Telegram bot UX."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.paging import encode as pg_encode

# ---------------------------------------------------------------------------
# Home menu
# ---------------------------------------------------------------------------

def home_menu() -> InlineKeyboardMarkup:
    """Main /start menu with a 3-column grid."""
    buttons = [
        [
            InlineKeyboardButton(text="Today", callback_data="cmd:today"),
            InlineKeyboardButton(text="7 days", callback_data="cmd:week"),
            InlineKeyboardButton(text="30 days", callback_data="cmd:month"),
        ],
        [
            InlineKeyboardButton(text="Weight", callback_data="cmd:weight"),
            InlineKeyboardButton(text="Steps", callback_data="cmd:steps"),
            InlineKeyboardButton(text="Sleep", callback_data="cmd:sleep"),
        ],
        [
            InlineKeyboardButton(text="Heart", callback_data="cmd:heart"),
            InlineKeyboardButton(text="Tables", callback_data="cmd:tables"),
            InlineKeyboardButton(text="Query", callback_data="cmd:query"),
        ],
        [
            InlineKeyboardButton(text="Health", callback_data="cmd:health"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def paginator(
    module: str,
    offset: int,
    page_size: int,
    total: int | None,
    extra: str = "",
) -> list[InlineKeyboardButton]:
    """Build a Prev / info / Next button row.

    *total* can be None when count is unknown (we still show Next if page full).
    """
    row: list[InlineKeyboardButton] = []

    if offset > 0:
        prev_off = max(0, offset - page_size)
        row.append(
            InlineKeyboardButton(
                text="<< Prev",
                callback_data=pg_encode(module, prev_off, extra),
            )
        )

    # Page indicator
    page_num = (offset // page_size) + 1
    if total is not None:
        total_pages = max(1, -(-total // page_size))  # ceil div
        row.append(
            InlineKeyboardButton(
                text=f"{page_num}/{total_pages}",
                callback_data="noop",
            )
        )
    else:
        row.append(
            InlineKeyboardButton(text=f"p.{page_num}", callback_data="noop")
        )

    next_off = offset + page_size
    show_next = total is None or next_off < total
    if show_next:
        row.append(
            InlineKeyboardButton(
                text="Next >>",
                callback_data=pg_encode(module, next_off, extra),
            )
        )

    return row


def paginated_keyboard(
    module: str,
    offset: int,
    page_size: int,
    total: int | None,
    extra: str = "",
    extra_buttons: list[list[InlineKeyboardButton]] | None = None,
) -> InlineKeyboardMarkup:
    """Full keyboard with optional extra button rows + pagination row."""
    rows: list[list[InlineKeyboardButton]] = []
    if extra_buttons:
        rows.extend(extra_buttons)
    rows.append(paginator(module, offset, page_size, total, extra))
    rows.append([back_button("cmd:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Drill-down & utility
# ---------------------------------------------------------------------------

def drill_down(items: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Build a list of buttons from (label, callback_data) tuples."""
    rows = [[InlineKeyboardButton(text=label, callback_data=cb)] for label, cb in items]
    rows.append([back_button("cmd:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_button(target: str = "cmd:start") -> InlineKeyboardButton:
    """Universal 'Back' button."""
    return InlineKeyboardButton(text="<< Back", callback_data=target)


def back_keyboard(target: str = "cmd:start") -> InlineKeyboardMarkup:
    """Keyboard with only a Back button."""
    return InlineKeyboardMarkup(inline_keyboard=[[back_button(target)]])


def confirm_buttons(yes_cb: str, no_cb: str = "cmd:start") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Yes", callback_data=yes_cb),
                InlineKeyboardButton(text="Cancel", callback_data=no_cb),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Domain-specific quick helpers
# ---------------------------------------------------------------------------

def weight_actions() -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(text="Trend", callback_data="wt:trend"),
            InlineKeyboardButton(text="Graph", callback_data="wt:graph"),
        ]
    ]


def steps_actions() -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(text="Graph", callback_data="st:graph"),
        ]
    ]


def period_drill(period: str) -> list[list[InlineKeyboardButton]]:
    """Buttons to drill into daily rows from a week/month summary."""
    return [
        [
            InlineKeyboardButton(
                text="Drill down (daily rows)",
                callback_data=f"drill:{period}:0",
            )
        ]
    ]


def table_actions(table_name: str) -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(
                text="Describe",
                callback_data=f"tbl:desc:{table_name}",
            ),
            InlineKeyboardButton(
                text="Browse",
                callback_data=pg_encode("brw", 0, table_name),
            ),
        ]
    ]
