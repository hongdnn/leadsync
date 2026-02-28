"""Demo users API router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from . import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr


@router.get("")
def list_users() -> list[dict]:
    """List users."""
    return user_service.list_users()


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
    return user_service.create_user(name=payload.name, email=str(payload.email))
