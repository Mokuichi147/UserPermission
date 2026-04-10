from pathlib import Path

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
    "connect",
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
    from .relay import RelayClient as RelayClient
    from .relay import RelayGroupManager as RelayGroupManager
    from .relay import RelayUserManager as RelayUserManager
    from .relay import create_relay_router as create_relay_router

    __all__ += [
        "RelayClient",
        "RelayGroupManager",
        "RelayUserManager",
        "create_relay_router",
    ]
except ImportError:
    pass


def connect(
    backend: str | Path, *, secret: str | Path | None = None
) -> "Database | RelayClient":
    """Create a backend by *backend* string.

    * File path (e.g. ``"user_permission.db"``) → local :class:`Database`
    * URL (e.g. ``"http://localhost:8001"``) → :class:`RelayClient`

    ``secret`` is only used in file mode (ignored for relay).
    """
    s = str(backend)
    if s.startswith(("http://", "https://")):
        from .relay import RelayClient as _Relay

        return _Relay(s)
    return Database(s, secret_key=secret)
