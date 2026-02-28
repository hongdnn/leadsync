"""Simple in-memory user service for demo purposes."""

from typing import Any


USERS: list[dict[str, Any]] = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin", "active": True},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "member", "active": True},
]


def _normalize(value: str) -> str:
    return value.strip().lower()


def list_users(
    *,
    q: str = "",
    active_only: bool = False,
    role: str = "",
    sort_by: str = "id",
    order: str = "asc",
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return users with basic filtering, sorting, and pagination."""
    items = USERS[:]

    if q.strip():
        query = _normalize(q)
        items = [
            user
            for user in items
            if query in _normalize(user["name"]) or query in _normalize(user["email"])
        ]
    if active_only:
        items = [user for user in items if bool(user.get("active", True))]
    if role.strip():
        wanted_role = _normalize(role)
        items = [user for user in items if _normalize(str(user.get("role", ""))) == wanted_role]

    allowed_sort = {"id", "name", "email", "role"}
    sort_key = sort_by if sort_by in allowed_sort else "id"
    reverse = order == "desc"
    items = sorted(items, key=lambda user: str(user.get(sort_key, "")), reverse=reverse)

    safe_offset = max(offset, 0)
    safe_limit = min(max(limit, 1), 200)
    return items[safe_offset : safe_offset + safe_limit]


def get_user(user_id: int) -> dict[str, Any] | None:
    """Return a user by id, or None."""
    for user in USERS:
        if user["id"] == user_id:
            return user
    return None


def create_user(name: str, email: str) -> dict[str, Any]:
    """Create and return a new user."""
    if email_exists(email):
        raise ValueError("Email already exists")
    new_id = max((u["id"] for u in USERS), default=0) + 1
    user = {
        "id": new_id,
        "name": name.strip(),
        "email": email.strip().lower(),
        "role": "member",
        "active": True,
    }
    USERS.append(user)
    return user


def email_exists(email: str, *, ignore_user_id: int | None = None) -> bool:
    """Return whether email already exists."""
    normalized = _normalize(email)
    for user in USERS:
        if ignore_user_id is not None and user["id"] == ignore_user_id:
            continue
        if _normalize(str(user.get("email", ""))) == normalized:
            return True
    return False


def update_user(
    user_id: int,
    *,
    name: str | None = None,
    email: str | None = None,
    role: str | None = None,
    active: bool | None = None,
) -> dict[str, Any] | None:
    """Partially update a user and return updated object."""
    user = get_user(user_id)
    if not user:
        return None

    if email is not None and email_exists(email, ignore_user_id=user_id):
        raise ValueError("Email already exists")

    if name is not None:
        user["name"] = name.strip()
    if email is not None:
        user["email"] = email.strip().lower()
    if role is not None:
        user["role"] = role.strip().lower()
    if active is not None:
        user["active"] = bool(active)
    return user


def deactivate_user(user_id: int) -> dict[str, Any] | None:
    """Soft-deactivate a user."""
    return update_user(user_id, active=False)


def user_stats() -> dict[str, int]:
    """Return simple user stats for dashboards."""
    total = len(USERS)
    active = sum(1 for user in USERS if bool(user.get("active", True)))
    inactive = total - active
    admins = sum(1 for user in USERS if str(user.get("role")) == "admin")
    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "admins": admins,
    }
