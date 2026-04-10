"""Relay client and router for forwarding requests to a central UserPermission server.

Usage – programmatic client::

    from user_permission.relay import RelayClient

    async with RelayClient("http://localhost:8001") as relay:
        token = await relay.login("alice", "password123")
        me = await relay.verify_token(token)

Usage – relay router in another FastAPI app::

    from user_permission.relay import RelayClient, create_relay_router

    relay = RelayClient("http://localhost:8001")

    @asynccontextmanager
    async def lifespan(app):
        await relay.connect()
        yield
        await relay.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(create_relay_router(relay, prefix="/auth"))
"""

from typing import Any

import httpx

from .group import Group
from .user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_from_dict(data: dict[str, Any]) -> User:
    return User(
        id=data["id"],
        username=data["username"],
        display_name=data["display_name"],
        is_active=data["is_active"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


def _group_from_dict(data: dict[str, Any]) -> Group:
    return Group(
        id=data["id"],
        name=data["name"],
        description=data["description"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# RelayClient
# ---------------------------------------------------------------------------

class RelayClient:
    """Async HTTP client that talks to a remote UserPermission server."""

    def __init__(self, base_url: str, *, prefix: str = "") -> None:
        self._base_url = base_url.rstrip("/") + prefix
        self._client: httpx.AsyncClient | None = None
        self.users = RelayUserManager(self)
        self.groups = RelayGroupManager(self)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "RelayClient is not connected. Call connect() first."
            )
        return self._client

    # -- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(base_url=self._base_url)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "RelayClient":
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # -- auth convenience ----------------------------------------------------

    async def login(self, username: str, password: str) -> str | None:
        """Authenticate against the remote server and return a JWT token."""
        resp = await self.client.post(
            "/token",
            data={"username": username, "password": password},
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]
        return None

    async def verify_token(self, token: str) -> User | None:
        """Verify *token* by calling ``GET /me`` on the remote server."""
        resp = await self.client.get("/me", headers=_bearer(token))
        if resp.status_code == 200:
            return _user_from_dict(resp.json())
        return None


# ---------------------------------------------------------------------------
# RelayUserManager
# ---------------------------------------------------------------------------

class RelayUserManager:
    """Mirrors :class:`UserManager` but forwards via HTTP."""

    def __init__(self, relay: RelayClient) -> None:
        self._relay = relay

    async def create(
        self, username: str, password: str, display_name: str = ""
    ) -> User | None:
        resp = await self._relay.client.post(
            "/users",
            json={
                "username": username,
                "password": password,
                "display_name": display_name,
            },
        )
        if resp.status_code == 201:
            return _user_from_dict(resp.json())
        return None

    async def get_by_id(self, user_id: int, token: str) -> User | None:
        resp = await self._relay.client.get(
            f"/users/{user_id}", headers=_bearer(token)
        )
        if resp.status_code == 200:
            return _user_from_dict(resp.json())
        return None

    async def list_all(self, token: str) -> list[User]:
        resp = await self._relay.client.get(
            "/users", headers=_bearer(token)
        )
        if resp.status_code == 200:
            return [_user_from_dict(u) for u in resp.json()]
        return []

    async def update(
        self,
        user_id: int,
        token: str,
        *,
        username: str | None = None,
        password: str | None = None,
        display_name: str | None = None,
        is_active: bool | None = None,
    ) -> User | None:
        body: dict[str, Any] = {}
        if username is not None:
            body["username"] = username
        if password is not None:
            body["password"] = password
        if display_name is not None:
            body["display_name"] = display_name
        if is_active is not None:
            body["is_active"] = is_active
        resp = await self._relay.client.patch(
            f"/users/{user_id}", json=body, headers=_bearer(token)
        )
        if resp.status_code == 200:
            return _user_from_dict(resp.json())
        return None

    async def delete(self, user_id: int, token: str) -> bool:
        resp = await self._relay.client.delete(
            f"/users/{user_id}", headers=_bearer(token)
        )
        return resp.status_code == 204

    async def authenticate(self, username: str, password: str) -> str | None:
        return await self._relay.login(username, password)


# ---------------------------------------------------------------------------
# RelayGroupManager
# ---------------------------------------------------------------------------

class RelayGroupManager:
    """Mirrors :class:`GroupManager` but forwards via HTTP."""

    def __init__(self, relay: RelayClient) -> None:
        self._relay = relay

    async def create(
        self, name: str, description: str, token: str
    ) -> Group | None:
        resp = await self._relay.client.post(
            "/groups",
            json={"name": name, "description": description},
            headers=_bearer(token),
        )
        if resp.status_code == 201:
            return _group_from_dict(resp.json())
        return None

    async def get_by_id(self, group_id: int, token: str) -> Group | None:
        resp = await self._relay.client.get(
            f"/groups/{group_id}", headers=_bearer(token)
        )
        if resp.status_code == 200:
            return _group_from_dict(resp.json())
        return None

    async def list_all(self, token: str) -> list[Group]:
        resp = await self._relay.client.get(
            "/groups", headers=_bearer(token)
        )
        if resp.status_code == 200:
            return [_group_from_dict(g) for g in resp.json()]
        return []

    async def update(
        self,
        group_id: int,
        token: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Group | None:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        resp = await self._relay.client.patch(
            f"/groups/{group_id}", json=body, headers=_bearer(token)
        )
        if resp.status_code == 200:
            return _group_from_dict(resp.json())
        return None

    async def delete(self, group_id: int, token: str) -> bool:
        resp = await self._relay.client.delete(
            f"/groups/{group_id}", headers=_bearer(token)
        )
        return resp.status_code == 204

    async def add_user(
        self, group_id: int, user_id: int, token: str
    ) -> bool:
        resp = await self._relay.client.post(
            f"/groups/{group_id}/members",
            json={"group_id": group_id, "user_id": user_id},
            headers=_bearer(token),
        )
        return resp.status_code == 201

    async def remove_user(
        self, group_id: int, user_id: int, token: str
    ) -> bool:
        resp = await self._relay.client.delete(
            f"/groups/{group_id}/members/{user_id}",
            headers=_bearer(token),
        )
        return resp.status_code == 204

    async def get_members(self, group_id: int, token: str) -> list[User]:
        resp = await self._relay.client.get(
            f"/groups/{group_id}/members", headers=_bearer(token)
        )
        if resp.status_code == 200:
            return [_user_from_dict(u) for u in resp.json()]
        return []

    async def get_user_groups(
        self, user_id: int, token: str
    ) -> list[Group]:
        resp = await self._relay.client.get(
            f"/users/{user_id}/groups", headers=_bearer(token)
        )
        if resp.status_code == 200:
            return [_group_from_dict(g) for g in resp.json()]
        return []


# ---------------------------------------------------------------------------
# Relay Router (transparent proxy for FastAPI apps)
# ---------------------------------------------------------------------------

_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)


def create_relay_router(
    relay: RelayClient,
    *,
    prefix: str = "",
) -> "APIRouter":  # type: ignore[name-defined]  # noqa: F821
    """Return a FastAPI router that transparently proxies every request
    to the remote UserPermission server via *relay*.

    Mount this in another FastAPI application to expose the full
    UserPermission API without a local database::

        app.include_router(create_relay_router(relay, prefix="/auth"))
    """
    from fastapi import APIRouter, Request
    from fastapi.responses import Response

    router = APIRouter(prefix=prefix)

    @router.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )
    async def _proxy(request: Request, path: str) -> Response:
        # Build forwarded headers (strip hop-by-hop & host).
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
        }

        upstream = await relay.client.request(
            method=request.method,
            url=f"/{path}",
            content=await request.body(),
            headers=headers,
        )

        # Strip hop-by-hop and content-encoding (already decoded by httpx).
        resp_headers = {
            k: v
            for k, v in upstream.headers.items()
            if k.lower() not in _HOP_BY_HOP
            and k.lower() != "content-encoding"
        }

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=resp_headers,
        )

    return router
