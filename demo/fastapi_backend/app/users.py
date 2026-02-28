"""Demo users API router."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from . import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr


class UpdateUserRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    email: EmailStr | None = None
    role: str | None = Field(default=None, min_length=3, max_length=20)
    active: bool | None = None


@router.get("")
def list_users(
    q: str = "",
    active_only: bool = False,
    role: str = "",
    sort_by: str = Query(default="id", pattern="^(id|name|email|role)$"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List users."""
    return user_service.list_users(
        q=q,
        active_only=active_only,
        role=role,
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}")
def get_user(user_id: int) -> dict:
    """Get one user by ID."""
    user = user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("", status_code=201)
def create_user(payload: CreateUserRequest) -> dict:
    """Create a user."""
    try:
        return user_service.create_user(name=payload.name, email=str(payload.email))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{user_id}")
def patch_user(user_id: int, payload: UpdateUserRequest) -> dict:
    """Partially update a user."""
    try:
        user = user_service.update_user(
            user_id,
            name=payload.name,
            email=str(payload.email) if payload.email is not None else None,
            role=payload.role,
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/{user_id}/deactivate")
def deactivate_user(user_id: int) -> dict:
    """Mark user as inactive."""
    user = user_service.deactivate_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/stats/summary")
def get_stats() -> dict:
    """Return lightweight user stats."""
    return user_service.user_stats()
