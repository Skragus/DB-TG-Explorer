"""Single-user authorization helpers."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def is_authorized(user_id: int | None, allowed_id: int) -> bool:
    """Return True if *user_id* matches the allowed Telegram user."""
    if user_id is None:
        return False
    return user_id == allowed_id
