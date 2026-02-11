from aiogram import Router
from bot.handlers.explorer import router as explorer_router

def register_all_routers() -> Router:
    """Create a root router and include all sub-routers."""
    root = Router(name="root")
    root.include_router(explorer_router)
    return root
