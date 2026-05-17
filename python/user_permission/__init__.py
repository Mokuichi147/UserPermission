"""Async user / group / permission management library.

The implementation now lives in a Rust extension module
(``user_permission._user_permission``); this package re-exports its public
API and adds a small Python entrypoint that calls the bundled server.
"""

from __future__ import annotations

from ._user_permission import (
    Database,
    Group,
    GroupManager,
    TokenManager,
    User,
    UserManager,
    __version__,
    hash_password,
    load_or_create_secret,
    serve,
    verify_password,
)

__all__ = [
    "Database",
    "Group",
    "GroupManager",
    "TokenManager",
    "User",
    "UserManager",
    "__version__",
    "hash_password",
    "load_or_create_secret",
    "serve",
    "verify_password",
]
