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


@patch("src.main.run_digest_crew")
def test_digest_trigger_success(mock_run, client):
    mock_run.return_value = MagicMock(raw="digest posted", model="gemini/gemini-2.5-flash")
    response = client.post("/digest/trigger")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["result"] == "digest posted"


@patch("src.main.run_digest_crew")
def test_digest_trigger_runtime_error_returns_400(mock_run, client):
    mock_run.side_effect = RuntimeError("Missing required env var: SLACK_CHANNEL_ID")
    response = client.post("/digest/trigger")
    assert response.status_code == 400
    assert "SLACK_CHANNEL_ID" in response.json()["detail"]


@patch("src.main.run_digest_crew")
def test_digest_trigger_unexpected_error_returns_500(mock_run, client):
    mock_run.side_effect = Exception("digest boom")
    response = client.post("/digest/trigger")
    assert response.status_code == 500
    assert "digest boom" in response.json()["detail"]


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
    mock_run.assert_called_once_with(
        ticket_key="LEADS-1",
        question="Should I use async?",
        thread_ts=None,
        channel_id=None,
    )


@patch("src.main.run_slack_crew")
def test_slack_command_form_encoded_success(mock_run, client):
    mock_run.return_value = MagicMock(raw="ok", model="gemini/gemini-2.5-flash")
    response = client.post(
        "/slack/commands",
        content=b"text=LEADS-2+Use+async%3F&thread_ts=1711111.1&channel_id=C123",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["response_type"] == "ephemeral"
    assert "LEADS-2" in data["text"]
    mock_run.assert_called_once_with(
        ticket_key="LEADS-2",
        question="Use async?",
        thread_ts="1711111.1",
        channel_id="C123",
    )


@patch("src.main.run_slack_crew")
def test_slack_command_json_text_parsing_success(mock_run, client):
    mock_run.return_value = MagicMock(raw="ok", model="gemini/gemini-2.5-flash")
    response = client.post(
        "/slack/commands",
        json={"text": "LEADS-3 Should we split this table?", "channel_id": "C123"},
    )
    assert response.status_code == 200
    mock_run.assert_called_once_with(
        ticket_key="LEADS-3",
        question="Should we split this table?",
        thread_ts=None,
        channel_id="C123",
    )


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
def test_slack_command_ssl_check_returns_ok_without_running_crew(mock_run, client):
    response = client.post(
        "/slack/commands",
        content=b"ssl_check=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_run.assert_not_called()


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


# ── /slack/prefs endpoint ───────────────────────────────────────────────────

@patch("src.main.append_preference")
def test_slack_prefs_add_success(mock_append, client):
    response = client.post(
        "/slack/prefs",
        content=b"text=add+Always+use+async",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["response_type"] == "ephemeral"
    assert "Always use async" in data["text"]
    mock_append.assert_called_once_with("Always use async")


@patch("src.main.append_preference")
def test_slack_prefs_empty_text_returns_400(mock_append, client):
    response = client.post(
        "/slack/prefs",
        content=b"text=",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    mock_append.assert_not_called()


@patch("src.main.append_preference")
def test_slack_prefs_ssl_check_returns_ok(mock_append, client):
    response = client.post(
        "/slack/prefs",
        content=b"ssl_check=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_append.assert_not_called()


@patch("src.main.append_preference")
def test_slack_prefs_unknown_command_returns_400(mock_append, client):
    response = client.post(
        "/slack/prefs",
        content=b"text=delete+everything",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    assert "Usage" in response.json()["detail"]
    mock_append.assert_not_called()


@patch("src.main.append_preference")
def test_slack_prefs_unexpected_error_returns_500(mock_append, client):
    mock_append.side_effect = Exception("disk error")
    response = client.post(
        "/slack/prefs",
        content=b"text=add+Some+rule",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 500
    assert "disk error" in response.json()["detail"]
