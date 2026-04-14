from .database import Database
from .group import Group, GroupManager
from .password import hash_password, verify_password
from .token import TokenManager, load_or_create_secret
from .user import User, UserManager

__all__ = [
    "Database",
    "Group",
    "GroupManager",
    "TokenManager",
    "User",
    "UserManager",
    "hash_password",
    "load_or_create_secret",
    "verify_password",
]

try:
    from .fastapi import create_router as create_router
    from .server import create_app as create_app

    __all__ += ["create_router", "create_app"]
except ImportError:
    pass

try:
    from .relay import create_relay_router as create_relay_router

    __all__ += ["create_relay_router"]
except ImportError:
    pass

try:
    from .webui import create_webui_router as create_webui_router

    __all__ += ["create_webui_router"]
except ImportError:
    pass
