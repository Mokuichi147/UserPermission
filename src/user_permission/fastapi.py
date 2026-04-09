from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from .database import Database
from .group import Group, GroupManager
from .token import TokenManager
from .user import User, UserManager


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
    created_at: str
    updated_at: str


class GroupCreate(BaseModel):
    name: str
    description: str = ""


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str
    created_at: str
    updated_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GroupMember(BaseModel):
    group_id: int
    user_id: int


# --- Helper ---


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _group_response(group: Group) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


# --- Router factory ---


def create_router(
    db: Database,
    token_manager: TokenManager,
    user_manager: UserManager,
    group_manager: GroupManager,
    *,
    prefix: str = "",
    token_url: str = "/token",
    token_expires: timedelta = timedelta(hours=1),
) -> APIRouter:
    router = APIRouter(prefix=prefix)
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl=prefix + token_url)

    async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
        try:
            payload: dict[str, Any] = token_manager.verify_token(token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = await user_manager.get_by_id(int(payload["sub"]))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        return user

    # --- Auth ---

    @router.post(token_url, response_model=TokenResponse)
    async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
        token = await user_manager.authenticate(
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
        return _user_response(current_user)

    # --- Users ---

    @router.post("/users", response_model=UserResponse, status_code=201)
    async def create_user(body: UserCreate) -> UserResponse:
        try:
            user = await user_manager.create(
                body.username, body.password, body.display_name
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )
        return _user_response(user)

    @router.get("/users", response_model=list[UserResponse])
    async def list_users(
        _: User = Depends(get_current_user),
    ) -> list[UserResponse]:
        users = await user_manager.list_all()
        return [_user_response(u) for u in users]

    @router.get("/users/{user_id}", response_model=UserResponse)
    async def get_user(
        user_id: int, _: User = Depends(get_current_user)
    ) -> UserResponse:
        user = await user_manager.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return _user_response(user)

    @router.patch("/users/{user_id}", response_model=UserResponse)
    async def update_user(
        user_id: int,
        body: UserUpdate,
        current_user: User = Depends(get_current_user),
    ) -> UserResponse:
        if current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Cannot update other users")
        user = await user_manager.update(
            user_id,
            username=body.username,
            password=body.password,
            display_name=body.display_name,
            is_active=body.is_active,
        )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return _user_response(user)

    @router.delete("/users/{user_id}", status_code=204)
    async def delete_user(
        user_id: int, current_user: User = Depends(get_current_user)
    ) -> None:
        if current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Cannot delete other users")
        if not await user_manager.delete(user_id):
            raise HTTPException(status_code=404, detail="User not found")

    # --- Groups ---

    @router.post("/groups", response_model=GroupResponse, status_code=201)
    async def create_group(
        body: GroupCreate, _: User = Depends(get_current_user)
    ) -> GroupResponse:
        try:
            group = await group_manager.create(body.name, body.description)
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
        groups = await group_manager.list_all()
        return [_group_response(g) for g in groups]

    @router.get("/groups/{group_id}", response_model=GroupResponse)
    async def get_group(
        group_id: int, _: User = Depends(get_current_user)
    ) -> GroupResponse:
        group = await group_manager.get_by_id(group_id)
        if group is None:
            raise HTTPException(status_code=404, detail="Group not found")
        return _group_response(group)

    @router.patch("/groups/{group_id}", response_model=GroupResponse)
    async def update_group(
        group_id: int,
        body: GroupUpdate,
        _: User = Depends(get_current_user),
    ) -> GroupResponse:
        group = await group_manager.update(
            group_id, name=body.name, description=body.description
        )
        if group is None:
            raise HTTPException(status_code=404, detail="Group not found")
        return _group_response(group)

    @router.delete("/groups/{group_id}", status_code=204)
    async def delete_group(
        group_id: int, _: User = Depends(get_current_user)
    ) -> None:
        if not await group_manager.delete(group_id):
            raise HTTPException(status_code=404, detail="Group not found")

    # --- Group members ---

    @router.post("/groups/{group_id}/members", status_code=201)
    async def add_member(
        group_id: int,
        body: GroupMember,
        _: User = Depends(get_current_user),
    ) -> dict[str, str]:
        if body.group_id != group_id:
            raise HTTPException(status_code=400, detail="group_id mismatch")
        if not await group_manager.add_user(group_id, body.user_id):
            raise HTTPException(status_code=409, detail="Already a member")
        return {"detail": "Member added"}

    @router.delete("/groups/{group_id}/members/{user_id}", status_code=204)
    async def remove_member(
        group_id: int,
        user_id: int,
        _: User = Depends(get_current_user),
    ) -> None:
        if not await group_manager.remove_user(group_id, user_id):
            raise HTTPException(status_code=404, detail="Member not found")

    @router.get("/groups/{group_id}/members", response_model=list[UserResponse])
    async def list_members(
        group_id: int, _: User = Depends(get_current_user)
    ) -> list[UserResponse]:
        members = await group_manager.get_members(group_id)
        return [_user_response(u) for u in members]

    @router.get("/users/{user_id}/groups", response_model=list[GroupResponse])
    async def list_user_groups(
        user_id: int, _: User = Depends(get_current_user)
    ) -> list[GroupResponse]:
        groups = await group_manager.get_user_groups(user_id)
        return [_group_response(g) for g in groups]

    return router
