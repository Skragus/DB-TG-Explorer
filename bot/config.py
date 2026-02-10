"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"FATAL: Missing required env var {name}", file=sys.stderr)
        sys.exit(1)
    return val


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    database_url: str
    allowed_user_id: int
    tz: ZoneInfo
    bot_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Rate-limit defaults
    rate_limit_max: int = 30  # max messages per window
    rate_limit_window: int = 60  # window in seconds

    # Pagination defaults
    page_size: int = 10
    browse_page_size: int = 20

    # Telegram message cap (leave margin for markup)
    max_message_len: int = 4000


def load_config() -> Config:
    """Build Config from env vars.  Exits on missing required vars."""
    return Config(
        bot_token=_require("TELEGRAM_BOT_TOKEN"),
        database_url=_require("DATABASE_URL"),
        allowed_user_id=int(_require("TG_ALLOWED_USER_ID")),
        tz=ZoneInfo(os.getenv("TZ", "Atlantic/Reykjavik")),
    )
