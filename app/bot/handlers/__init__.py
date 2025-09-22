from .commands import user_router
from .admin_commands import admin_router
from .callbacks import callback_router
__all__ = ["user_router", "admin_router", "callback_router"]