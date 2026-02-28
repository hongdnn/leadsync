"""Simple in-memory user service for demo purposes."""

from typing import Any


USERS: list[dict[str, Any]] = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"},
]


def list_users() -> list[dict[str, Any]]:
    """Return all users."""
    return USERS


def get_user(user_id: int) -> dict[str, Any] | None:
    """Return a user by id, or None."""
    for user in USERS:
        if user["id"] == user_id:
            return user
    return None


def create_user(name: str, email: str) -> dict[str, Any]:
    """Create and return a new user."""
    new_id = max((u["id"] for u in USERS), default=0) + 1
    user = {"id": new_id, "name": name, "email": email}
    USERS.append(user)
    return user
