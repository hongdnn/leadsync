"""Tests for demo users API."""

from fastapi.testclient import TestClient

from demo.fastapi_backend.app.main import app

client = TestClient(app)


def test_list_users() -> None:
    response = client.get("/api/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


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
