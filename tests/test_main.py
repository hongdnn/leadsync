"""
tests/test_main.py
Unit tests for src/main.py — FastAPI endpoints.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("src.main.run_leadsync_crew")
def test_jira_webhook_success(mock_run, client):
    mock_run.return_value = MagicMock(raw="done", model="gemini/gemini-2.5-flash")
    payload = {"issue": {"key": "LEADS-1", "fields": {}}}
    response = client.post("/webhooks/jira", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["model"] == "gemini/gemini-2.5-flash"
    assert data["result"] == "done"


@patch("src.main.run_leadsync_crew")
def test_jira_webhook_runtime_error_returns_400(mock_run, client):
    mock_run.side_effect = RuntimeError("Missing required env var: COMPOSIO_API_KEY")
    response = client.post("/webhooks/jira", json={})
    assert response.status_code == 400
    assert "COMPOSIO_API_KEY" in response.json()["detail"]


@patch("src.main.run_leadsync_crew")
def test_jira_webhook_unexpected_error_returns_500(mock_run, client):
    mock_run.side_effect = Exception("unexpected failure")
    response = client.post("/webhooks/jira", json={})
    assert response.status_code == 500
    assert "unexpected failure" in response.json()["detail"]


@patch("src.main.run_slack_crew")
def test_slack_command_json_success(mock_run, client):
    mock_run.return_value = MagicMock(raw="reply posted", model="gemini/gemini-2.5-flash")
    response = client.post(
        "/slack/commands",
        json={"ticket_key": "LEADS-1", "question": "Should I use async?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["result"] == "reply posted"
    mock_run.assert_called_once_with(ticket_key="LEADS-1", question="Should I use async?")


@patch("src.main.run_slack_crew")
def test_slack_command_form_encoded_success(mock_run, client):
    mock_run.return_value = MagicMock(raw="ok", model="gemini/gemini-2.5-flash")
    response = client.post(
        "/slack/commands",
        content=b"text=LEADS-2+Use+async%3F",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    mock_run.assert_called_once_with(ticket_key="LEADS-2", question="Use async?")


@patch("src.main.run_slack_crew")
def test_slack_command_missing_ticket_key_returns_400(mock_run, client):
    response = client.post(
        "/slack/commands",
        json={"question": "something"},
    )
    assert response.status_code == 400
    assert "ticket_key" in response.json()["detail"]


@patch("src.main.run_slack_crew")
def test_slack_command_empty_form_text_returns_400(mock_run, client):
    response = client.post(
        "/slack/commands",
        content=b"text=",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


@patch("src.main.run_slack_crew")
def test_slack_command_runtime_error_returns_400(mock_run, client):
    mock_run.side_effect = RuntimeError("Missing required env var: SLACK_CHANNEL_ID")
    response = client.post(
        "/slack/commands",
        json={"ticket_key": "LEADS-1", "question": "test"},
    )
    assert response.status_code == 400
    assert "SLACK_CHANNEL_ID" in response.json()["detail"]


@patch("src.main.run_slack_crew")
def test_slack_command_unexpected_error_returns_500(mock_run, client):
    mock_run.side_effect = Exception("boom")
    response = client.post(
        "/slack/commands",
        json={"ticket_key": "LEADS-1", "question": "test"},
    )
    assert response.status_code == 500
    assert "boom" in response.json()["detail"]
