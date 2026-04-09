from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .database import Database
from .password import hash_password, verify_password
from .token import TokenManager


@dataclass
class User:
    id: int
    username: str
    display_name: str
    is_active: bool
    created_at: str
    updated_at: str


class UserManager:
    def __init__(self, db: Database, token_manager: TokenManager) -> None:
        self._db = db
        self._token_manager = token_manager

    def _row_to_user(self, row: Any) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def create(
        self, username: str, password: str, display_name: str = ""
    ) -> User:
        hashed = hash_password(password)
        conn = self._db.connection
        cursor = await conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            (username, hashed, display_name),
        )
        await conn.commit()
        row = await (
            await conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,))
        ).fetchone()
        return self._row_to_user(row)

    async def get_by_id(self, user_id: int) -> User | None:
        row = await (
            await self._db.connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            )
        ).fetchone()
        return self._row_to_user(row) if row else None

    async def get_by_username(self, username: str) -> User | None:
        row = await (
            await self._db.connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            )
        ).fetchone()
        return self._row_to_user(row) if row else None

    async def list_all(self) -> list[User]:
        rows = await (
            await self._db.connection.execute("SELECT * FROM users ORDER BY id")
        ).fetchall()
        return [self._row_to_user(r) for r in rows]

    async def update(
        self,
        user_id: int,
        *,
        username: str | None = None,
        password: str | None = None,
        display_name: str | None = None,
        is_active: bool | None = None,
    ) -> User | None:
        fields: list[str] = []
        values: list[Any] = []
        if username is not None:
            fields.append("username = ?")
            values.append(username)
        if password is not None:
            fields.append("password_hash = ?")
            values.append(hash_password(password))
        if display_name is not None:
            fields.append("display_name = ?")
            values.append(display_name)
        if is_active is not None:
            fields.append("is_active = ?")
            values.append(int(is_active))
        if not fields:
            return await self.get_by_id(user_id)
        fields.append("updated_at = datetime('now')")
        values.append(user_id)
        conn = self._db.connection
        await conn.execute(
            f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values
        )
        await conn.commit()
        return await self.get_by_id(user_id)

    async def delete(self, user_id: int) -> bool:
        conn = self._db.connection
        cursor = await conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def authenticate(
        self,
        username: str,
        password: str,
        expires_delta: timedelta = timedelta(hours=1),
    ) -> str | None:
        row = await (
            await self._db.connection.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,),
            )
        ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        return self._token_manager.create_token(
            user_id=row["id"],
            username=row["username"],
            expires_delta=expires_delta,
        )
