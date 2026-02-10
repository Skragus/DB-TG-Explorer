"""Aiogram middleware: auth guard + rate limiter."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from bot.utils.security import is_authorized

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth middleware  (outer middleware -- runs on every update)
# ---------------------------------------------------------------------------


class AuthMiddleware(BaseMiddleware):
    """Block updates from unauthorised users."""

    def __init__(self, allowed_user_id: int) -> None:
        self.allowed_user_id = allowed_user_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        user_id = user.id if user else None

        if not is_authorized(user_id, self.allowed_user_id):
            logger.warning("Auth denied for user_id=%s", user_id)
            # Try to send a denial if the event is a message or callback
            if isinstance(event, Message):
                await event.answer("Sorry, this bot is private.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Access denied.", show_alert=True)
            return  # halt handler chain

        return await handler(event, data)


# ---------------------------------------------------------------------------
# Rate-limit middleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseMiddleware):
    """Simple sliding-window rate limiter.

    Tracks message timestamps per user and rejects if the window is exceeded.
    """

    def __init__(self, max_calls: int = 30, window_seconds: int = 60) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._timestamps: dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        uid = user.id
        now = time.monotonic()
        # Purge old timestamps
        cutoff = now - self.window
        self._timestamps[uid] = [t for t in self._timestamps[uid] if t > cutoff]

        if len(self._timestamps[uid]) >= self.max_calls:
            logger.warning("Rate limit hit for user_id=%s", uid)
            if isinstance(event, Message):
                await event.answer("Slow down! Too many requests.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Too many requests. Wait a moment.", show_alert=True)
            return

        self._timestamps[uid].append(now)
        return await handler(event, data)
