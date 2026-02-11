from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from aiogram.filters.callback_data import CallbackData


class ExplorerCB(CallbackData, prefix="x"):
    """Callback data for explorer navigation.
    
    Short keys to save space (64 bytes limit).
    a: action (l=list, t=table, r=rows, d=detail)
    t: table
    p: page
    k: pk_val
    """
    a: Literal["l", "t", "r", "d"]
    t: str | None = None
    p: int = 0
    k: str | None = None


@dataclass(frozen=True)
class Paginator:
    total_items: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.total_items == 0:
            return 1
        return math.ceil(self.total_items / self.page_size)

    @property
    def has_next(self) -> int:
        return self.page < self.total_pages - 1

    @property
    def has_prev(self) -> int:
        return self.page > 0

    @property
    def offset(self) -> int:
        return self.page * self.page_size

    @property
    def slice_end(self) -> int:
        return min(self.offset + self.page_size, self.total_items)


def build_breadcrumbs(table: str | None = None, row_pk: str | None = None) -> str:
    parts = ["🏠 Database"]
    if table:
        parts.append(f"📂 {table}")
    if row_pk:
        parts.append(f"📄 {row_pk}")
    return " > ".join(parts)
