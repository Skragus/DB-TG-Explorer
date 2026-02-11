"""Bot entrypoint.  Run with: python -m bot.main"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot import db
from bot.config import Config, load_config
from bot.middleware import AuthMiddleware, RateLimitMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)





async def main() -> None:
    cfg = load_config()
    logger.info("Starting DB-TG-Explorer bot  (tz=%s)", cfg.tz)

    # ---- Database ----
    await db.create_pool(cfg.database_url)

    # ---- Bot + Dispatcher ----
    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Inject config into handler data so handlers can access it via `config: Config`
    dp["config"] = cfg

    # ---- Middleware (outer -> inner) ----
    dp.message.outer_middleware(AuthMiddleware(cfg.allowed_user_id))
    dp.callback_query.outer_middleware(AuthMiddleware(cfg.allowed_user_id))
    dp.message.middleware(RateLimitMiddleware(cfg.rate_limit_max, cfg.rate_limit_window))
    dp.callback_query.middleware(RateLimitMiddleware(cfg.rate_limit_max, cfg.rate_limit_window))

    # ---- Routers ----
    from bot.handlers import explorer
    dp.include_router(explorer.router)

    # ---- Callback no-op handler (for info-only buttons) ----
    @dp.callback_query(lambda cb: cb.data == "noop")
    async def _noop(callback) -> None:
        await callback.answer()

    # ---- Start polling ----
    logger.info("Bot is polling...")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await db.close_pool()
        await bot.session.close()
        logger.info("Bot shut down.")


if __name__ == "__main__":
    asyncio.run(main())
