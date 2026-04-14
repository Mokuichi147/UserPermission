from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .database import Database
from .password import hash_password, verify_password


@dataclass
class User:
    id: int
    username: str
    display_name: str
    is_active: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Any) -> "User":
        return cls(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class UserManager:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self, username: str, password: str, display_name: str = ""
    ) -> User:
        hashed = hash_password(password)
        conn = self._db.connection
        is_first = (
            await (await conn.execute("SELECT COUNT(*) AS c FROM users")).fetchone()
        )["c"] == 0
        cursor = await conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            (username, hashed, display_name),
        )
        user_id = cursor.lastrowid
        if is_first:
            admin_row = await (
                await conn.execute("SELECT id FROM groups WHERE name = ?", ("admin",))
            ).fetchone()
            if admin_row is None:
                admin_cursor = await conn.execute(
                    "INSERT INTO groups (name, description, is_admin) VALUES (?, ?, 1)",
                    ("admin", "UserPermission 管理者"),
                )
                admin_group_id = admin_cursor.lastrowid
            else:
                admin_group_id = admin_row["id"]
                await conn.execute(
                    "UPDATE groups SET is_admin = 1 WHERE id = ?", (admin_group_id,)
                )
            await conn.execute(
                "INSERT OR IGNORE INTO user_groups (user_id, group_id) VALUES (?, ?)",
                (user_id, admin_group_id),
            )
        await conn.commit()
        row = await (
            await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        ).fetchone()
        return User.from_row(row)

    async def get_by_id(self, user_id: int) -> User | None:
        row = await (
            await self._db.connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            )
        ).fetchone()
        return User.from_row(row) if row else None

    async def get_by_username(self, username: str) -> User | None:
        row = await (
            await self._db.connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            )
        ).fetchone()
        return User.from_row(row) if row else None

    async def list_all(self) -> list[User]:
        rows = await (
            await self._db.connection.execute("SELECT * FROM users ORDER BY id")
        ).fetchall()
        return [User.from_row(r) for r in rows]

    async def is_admin(self, user_id: int) -> bool:
        row = await (
            await self._db.connection.execute(
                """
                SELECT 1 FROM user_groups ug
                JOIN groups g ON ug.group_id = g.id
                WHERE ug.user_id = ? AND g.is_admin = 1
                LIMIT 1
                """,
                (user_id,),
            )
        ).fetchone()
        return row is not None

    async def set_admin(self, user_id: int, is_admin: bool) -> bool:
        """ユーザーを管理者グループに加入/脱退させて昇格/降格する。

        昇格: ``name = 'admin'`` のグループを探し、無ければ作成して加入。
        降格: ``is_admin = 1`` のグループ全てから脱退。
        """
        conn = self._db.connection
        if is_admin:
            row = await (
                await conn.execute(
                    "SELECT id FROM groups WHERE name = ? AND is_admin = 1", ("admin",)
                )
            ).fetchone()
            if row is None:
                row = await (
                    await conn.execute(
                        "SELECT id FROM groups WHERE is_admin = 1 ORDER BY id LIMIT 1"
                    )
                ).fetchone()
            if row is None:
                cursor = await conn.execute(
                    "INSERT INTO groups (name, description, is_admin) VALUES (?, ?, 1)",
                    ("admin", "UserPermission 管理者"),
                )
                group_id = cursor.lastrowid
            else:
                group_id = row["id"]
            await conn.execute(
                "INSERT OR IGNORE INTO user_groups (user_id, group_id) VALUES (?, ?)",
                (user_id, group_id),
            )
        else:
            await conn.execute(
                """
                DELETE FROM user_groups
                WHERE user_id = ?
                AND group_id IN (SELECT id FROM groups WHERE is_admin = 1)
                """,
                (user_id,),
            )
        await conn.commit()
        return True

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
        is_admin = await self.is_admin(row["id"])
        return self._db.token_manager.create_token(
            user_id=row["id"],
            username=row["username"],
            expires_delta=expires_delta,
            extra_claims={"is_admin": is_admin},
        )
