from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from .database import Database
from .group import Group
from .user import User


# --- Pydantic schemas ---


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""


class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    display_name: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    is_active: bool
    is_admin: bool
    created_at: str
    updated_at: str


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    is_admin: bool = False


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_admin: bool | None = None


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str
    is_admin: bool
    created_at: str
    updated_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GroupMember(BaseModel):
    group_id: int
    user_id: int


# --- Helper ---


def _user_response(user: User, is_admin: bool) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        is_admin=is_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _group_response(group: Group) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        is_admin=group.is_admin,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


# --- Router factory ---


def create_router(
    db: Database,
    *,
    prefix: str = "",
    token_url: str = "/token",
    token_expires: timedelta = timedelta(hours=1),
) -> APIRouter:
    router = APIRouter(prefix=prefix)
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl=prefix + token_url)

    async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
        try:
            payload: dict[str, Any] = db.token_manager.verify_token(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = await db.users.get_by_id(int(payload["sub"]))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        return user

    async def get_admin_user(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not await db.users.is_admin(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )
        return current_user

    # --- Auth ---

    @router.post(token_url, response_model=TokenResponse)
    async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
        token = await db.users.authenticate(
            form.username, form.password, expires_delta=token_expires
        )
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenResponse(access_token=token)

    @router.get("/me", response_model=UserResponse)
    async def read_current_user(
        current_user: User = Depends(get_current_user),
    ) -> UserResponse:
        is_admin = await db.users.is_admin(current_user.id)
        return _user_response(current_user, is_admin)

    # --- Users ---

    @router.post("/users", response_model=UserResponse, status_code=201)
    async def create_user(body: UserCreate) -> UserResponse:
        try:
            user = await db.users.create(
                body.username, body.password, body.display_name
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )
        is_admin = await db.users.is_admin(user.id)
        return _user_response(user, is_admin)

    @router.get("/users", response_model=list[UserResponse])
    async def list_users(
        _: User = Depends(get_current_user),
    ) -> list[UserResponse]:
        users = await db.users.list_all()
        return [_user_response(u, await db.users.is_admin(u.id)) for u in users]

    @router.get("/users/{user_id}", response_model=UserResponse)
    async def get_user(
        user_id: int, _: User = Depends(get_current_user)
    ) -> UserResponse:
        user = await db.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return _user_response(user, await db.users.is_admin(user.id))

    @router.patch("/users/{user_id}", response_model=UserResponse)
    async def update_user(
        user_id: int,
        body: UserUpdate,
        current_user: User = Depends(get_current_user),
    ) -> UserResponse:
        caller_is_admin = await db.users.is_admin(current_user.id)
        if current_user.id != user_id and not caller_is_admin:
            raise HTTPException(
                status_code=403, detail="Admin privileges required"
            )
        try:
            user = await db.users.update(
                user_id,
                username=body.username,
                password=body.password,
                display_name=body.display_name,
                is_active=body.is_active,
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return _user_response(user, await db.users.is_admin(user.id))

    @router.delete("/users/{user_id}", status_code=204)
    async def delete_user(
        user_id: int, current_user: User = Depends(get_current_user)
    ) -> None:
        caller_is_admin = await db.users.is_admin(current_user.id)
        if current_user.id != user_id and not caller_is_admin:
            raise HTTPException(
                status_code=403, detail="Admin privileges required"
            )
        if not await db.users.delete(user_id):
            raise HTTPException(status_code=404, detail="User not found")

    # --- Groups ---

    @router.post("/groups", response_model=GroupResponse, status_code=201)
    async def create_group(
        body: GroupCreate, _: User = Depends(get_admin_user)
    ) -> GroupResponse:
        try:
            group = await db.groups.create(
                body.name, body.description, is_admin=body.is_admin
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Group name already exists",
            )
        return _group_response(group)

    @router.get("/groups", response_model=list[GroupResponse])
    async def list_groups(
        _: User = Depends(get_current_user),
    ) -> list[GroupResponse]:
        groups = await db.groups.list_all()
        return [_group_response(g) for g in groups]

    @router.get("/groups/{group_id}", response_model=GroupResponse)
    async def get_group(
        group_id: int, _: User = Depends(get_current_user)
    ) -> GroupResponse:
        group = await db.groups.get_by_id(group_id)
        if group is None:
            raise HTTPException(status_code=404, detail="Group not found")
        return _group_response(group)

    @router.patch("/groups/{group_id}", response_model=GroupResponse)
    async def update_group(
        group_id: int,
        body: GroupUpdate,
        _: User = Depends(get_admin_user),
    ) -> GroupResponse:
        group = await db.groups.update(
            group_id,
            name=body.name,
            description=body.description,
            is_admin=body.is_admin,
        )
        if group is None:
            raise HTTPException(status_code=404, detail="Group not found")
        return _group_response(group)

    @router.delete("/groups/{group_id}", status_code=204)
    async def delete_group(
        group_id: int, _: User = Depends(get_admin_user)
    ) -> None:
        if not await db.groups.delete(group_id):
            raise HTTPException(status_code=404, detail="Group not found")

    # --- Group members ---

    @router.post("/groups/{group_id}/members", status_code=201)
    async def add_member(
        group_id: int,
        body: GroupMember,
        _: User = Depends(get_admin_user),
    ) -> dict[str, str]:
        if body.group_id != group_id:
            raise HTTPException(status_code=400, detail="group_id mismatch")
        if not await db.groups.add_user(group_id, body.user_id):
            raise HTTPException(status_code=409, detail="Already a member")
        return {"detail": "Member added"}

    @router.delete("/groups/{group_id}/members/{user_id}", status_code=204)
    async def remove_member(
        group_id: int,
        user_id: int,
        _: User = Depends(get_admin_user),
    ) -> None:
        if not await db.groups.remove_user(group_id, user_id):
            raise HTTPException(status_code=404, detail="Member not found")

    @router.get("/groups/{group_id}/members", response_model=list[UserResponse])
    async def list_members(
        group_id: int, _: User = Depends(get_current_user)
    ) -> list[UserResponse]:
        members = await db.groups.get_members(group_id)
        return [
            _user_response(u, await db.users.is_admin(u.id)) for u in members
        ]

    @router.get("/users/{user_id}/groups", response_model=list[GroupResponse])
    async def list_user_groups(
        user_id: int, _: User = Depends(get_current_user)
    ) -> list[GroupResponse]:
        groups = await db.groups.get_user_groups(user_id)
        return [_group_response(g) for g in groups]

    return router
