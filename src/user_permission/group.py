from dataclasses import dataclass
from typing import Any

from .database import Database
from .user import User, UserManager


@dataclass
class Group:
    id: int
    name: str
    description: str
    created_at: str
    updated_at: str


class GroupManager:
    def __init__(self, db: Database, user_manager: UserManager) -> None:
        self._db = db
        self._user_manager = user_manager

    def _row_to_group(self, row: Any) -> Group:
        return Group(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def create(self, name: str, description: str = "") -> Group:
        conn = self._db.connection
        cursor = await conn.execute(
            "INSERT INTO groups (name, description) VALUES (?, ?)",
            (name, description),
        )
        await conn.commit()
        row = await (
            await conn.execute("SELECT * FROM groups WHERE id = ?", (cursor.lastrowid,))
        ).fetchone()
        return self._row_to_group(row)

    async def get_by_id(self, group_id: int) -> Group | None:
        row = await (
            await self._db.connection.execute(
                "SELECT * FROM groups WHERE id = ?", (group_id,)
            )
        ).fetchone()
        return self._row_to_group(row) if row else None

    async def get_by_name(self, name: str) -> Group | None:
        row = await (
            await self._db.connection.execute(
                "SELECT * FROM groups WHERE name = ?", (name,)
            )
        ).fetchone()
        return self._row_to_group(row) if row else None

    async def list_all(self) -> list[Group]:
        rows = await (
            await self._db.connection.execute("SELECT * FROM groups ORDER BY id")
        ).fetchall()
        return [self._row_to_group(r) for r in rows]

    async def update(
        self,
        group_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Group | None:
        fields: list[str] = []
        values: list[Any] = []
        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if description is not None:
            fields.append("description = ?")
            values.append(description)
        if not fields:
            return await self.get_by_id(group_id)
        fields.append("updated_at = datetime('now')")
        values.append(group_id)
        conn = self._db.connection
        await conn.execute(
            f"UPDATE groups SET {', '.join(fields)} WHERE id = ?", values
        )
        await conn.commit()
        return await self.get_by_id(group_id)

    async def delete(self, group_id: int) -> bool:
        conn = self._db.connection
        cursor = await conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        await conn.commit()
        return cursor.rowcount > 0

    async def add_user(self, group_id: int, user_id: int) -> bool:
        conn = self._db.connection
        try:
            await conn.execute(
                "INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)",
                (user_id, group_id),
            )
            await conn.commit()
            return True
        except Exception:
            return False

    async def remove_user(self, group_id: int, user_id: int) -> bool:
        conn = self._db.connection
        cursor = await conn.execute(
            "DELETE FROM user_groups WHERE user_id = ? AND group_id = ?",
            (user_id, group_id),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def get_members(self, group_id: int) -> list[User]:
        rows = await (
            await self._db.connection.execute(
                """
                SELECT u.* FROM users u
                JOIN user_groups ug ON u.id = ug.user_id
                WHERE ug.group_id = ?
                ORDER BY u.id
                """,
                (group_id,),
            )
        ).fetchall()
        return [self._user_manager._row_to_user(r) for r in rows]

    async def get_user_groups(self, user_id: int) -> list[Group]:
        rows = await (
            await self._db.connection.execute(
                """
                SELECT g.* FROM groups g
                JOIN user_groups ug ON g.id = ug.group_id
                WHERE ug.user_id = ?
                ORDER BY g.id
                """,
                (user_id,),
            )
        ).fetchall()
        return [self._row_to_group(r) for r in rows]
