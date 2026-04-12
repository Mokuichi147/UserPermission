from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from .token import TokenManager

if TYPE_CHECKING:
    from .group import GroupManager
    from .user import UserManager


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_groups (
    user_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, group_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);
"""


def _is_url(backend: str | Path) -> bool:
    return str(backend).startswith(("http://", "https://"))


class Database:
    """ユーザー権限バックエンドの統一エントリポイント。

    * ファイルパス(例: ``"app.db"``) → ローカル SQLite データベース
    * URL(例: ``"http://localhost:8001"``) → リモートサーバーへの HTTP リレー

    どちらの場合も ``db.users`` / ``db.groups`` で同じ操作 API が使えます。
    """

    def __new__(
        cls, backend: str | Path, *, secret: str | Path | None = None
    ) -> "Database":
        if cls is not Database:
            return super().__new__(cls)
        if _is_url(backend):
            if secret is not None:
                raise ValueError(
                    "secret は HTTP バックエンドでは利用できません"
                )
            from .relay import _RelayDatabase

            return super().__new__(_RelayDatabase)
        return super().__new__(_LocalDatabase)

    async def connect(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


class _LocalDatabase(Database):
    def __init__(
        self, backend: str | Path, *, secret: str | Path | None = None
    ) -> None:
        self._db_path = str(backend)
        self._connection: aiosqlite.Connection | None = None
        self._token_manager: TokenManager | None = None
        if secret is not None:
            self._token_manager = TokenManager.from_file(secret)

        from .group import GroupManager
        from .user import UserManager

        self.users: UserManager = UserManager(self)
        self.groups: GroupManager = GroupManager(self)

    @property
    def token_manager(self) -> TokenManager:
        if self._token_manager is None:
            raise RuntimeError("Database() に secret が渡されていません。")
        return self._token_manager

    async def connect(self) -> None:
        self._connection = await aiosqlite.connect(self._db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        await self._connection.executescript(_SCHEMA_SQL)
        await self._connection.commit()

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError(
                "Database is not connected. Call connect() first."
            )
        return self._connection
