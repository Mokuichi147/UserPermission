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
    webui: bool = False,
    webui_prefix: str = "/ui",
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
    webui:
        True にすると HTMX + Tailwind + Jinja2 の管理画面を有効化する。
    webui_prefix:
        管理画面のURLプレフィックス（デフォルト: ``"/ui"``）。
    """
    db = Database(database, secret=secret)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await db.connect()
        yield
        await db.close()

    app = FastAPI(title="UserPermission", lifespan=lifespan)
    app.include_router(create_router(db, prefix=prefix))
    if webui:
        from fastapi.responses import RedirectResponse

        from .webui import create_webui_router

        app.include_router(create_webui_router(db, prefix=webui_prefix))

        if prefix != "" or webui_prefix != "":
            @app.get("/", include_in_schema=False)
            async def _root() -> RedirectResponse:
                return RedirectResponse(webui_prefix + "/")
    return app
