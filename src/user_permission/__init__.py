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

    __all__.append("create_router")
except ImportError:
    pass
