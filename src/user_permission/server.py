from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from . import connect
from .database import Database


def create_app(
    *,
    backend: str = "user_permission.db",
    secret: str = "secret.key",
    prefix: str = "",
) -> FastAPI:
    """Create a standalone UserPermission FastAPI application.

    Parameters
    ----------
    backend:
        File path for local SQLite mode, or URL for relay mode.
        (e.g. ``"user_permission.db"`` or ``"http://localhost:8001"``)
    secret:
        Path to the secret-key file (local mode only; ignored in relay).
    prefix:
        URL prefix for all API routes (e.g. ``"/api"``).
    """
    source = connect(backend, secret=secret)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await source.connect()
        yield
        await source.close()

    app = FastAPI(title="UserPermission", lifespan=lifespan)

    if isinstance(source, Database):
        from .fastapi import create_router

        app.include_router(create_router(source, prefix=prefix))
    else:
        from .relay import create_relay_router

        app.include_router(create_relay_router(source, prefix=prefix))

    return app
