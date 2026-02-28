"""Tests for demo users API."""

from fastapi.testclient import TestClient

from demo.fastapi_backend.app.main import app

client = TestClient(app)


def test_list_users() -> None:
    response = client.get("/api/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_users_filters_and_sorting() -> None:
    response = client.get(
        "/api/users",
        params={
            "q": "alice",
            "active_only": "true",
            "sort_by": "name",
            "order": "asc",
            "limit": 10,
            "offset": 0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any("alice" in user["email"] for user in data)


def test_get_user_not_found() -> None:
    response = client.get("/api/users/9999")
    assert response.status_code == 404


def test_create_user() -> None:
    response = client.post(
        "/api/users",
        json={"name": "Charlie", "email": "charlie@example.com"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Charlie"
    assert body["email"] == "charlie@example.com"
    assert body["role"] == "member"
    assert body["active"] is True


def test_create_user_duplicate_email_returns_409() -> None:
    response = client.post(
        "/api/users",
        json={"name": "Alice Clone", "email": "alice@example.com"},
    )
    assert response.status_code == 409


def test_patch_user_success() -> None:
    response = client.patch(
        "/api/users/2",
        json={"name": "Bobby", "role": "admin"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Bobby"
    assert body["role"] == "admin"


def test_patch_user_duplicate_email_conflict() -> None:
    response = client.patch(
        "/api/users/2",
        json={"email": "alice@example.com"},
    )
    assert response.status_code == 409


def test_deactivate_user() -> None:
    response = client.post("/api/users/2/deactivate")
    assert response.status_code == 200
    body = response.json()
    assert body["active"] is False


def test_stats_summary() -> None:
    response = client.get("/api/users/stats/summary")
    assert response.status_code == 200
    body = response.json()
    assert "total" in body
    assert "active" in body
    assert "inactive" in body
    assert "admins" in body
