"""Handler routers registration."""

from aiogram import Router

from bot.handlers import (
    health,
    heart,
    period,
    query,
    sleep,
    start,
    steps,
    tables,
    today,
    weight,
)


def register_all_routers() -> Router:
    """Create a root router and include all sub-routers."""
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(health.router)
    root.include_router(today.router)
    root.include_router(period.router)
    root.include_router(weight.router)
    root.include_router(steps.router)
    root.include_router(sleep.router)
    root.include_router(heart.router)
    root.include_router(tables.router)
    root.include_router(query.router)
    return root
