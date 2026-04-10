from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from .database import Database
from .fastapi import create_router


def create_app(
    *,
    database: str = "user_permission.db",
    secret: str = "secret.key",
    prefix: str = "",
) -> FastAPI:
    """Create a standalone UserPermission FastAPI application.

    Parameters
    ----------
    database:
        Path to the SQLite database file.
    secret:
        Path to the secret-key file (auto-created if missing).
    prefix:
        URL prefix for all API routes (e.g. ``"/api"``).
    """
    db = Database(database, secret_key=secret)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await db.connect()
        yield
        await db.close()

    app = FastAPI(title="UserPermission", lifespan=lifespan)
    app.include_router(create_router(db, prefix=prefix))
    return app
