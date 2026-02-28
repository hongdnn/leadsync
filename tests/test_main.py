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


@pytest.fixture(autouse=True)
def clear_digest_trigger_token(monkeypatch):
    """Keep endpoint tests deterministic regardless of developer shell env vars."""
    monkeypatch.delenv("LEADSYNC_TRIGGER_TOKEN", raising=False)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("src.main.memory_enabled", return_value=True)
@patch("src.main.build_memory_db_path", return_value=":memory:")
@patch("src.main.init_memory_db")
def test_initialize_memory_calls_db_init(mock_init_db, mock_db_path, mock_enabled):
    from src.main import initialize_memory

    initialize_memory()
    mock_init_db.assert_called_once_with(":memory:")


@patch("src.main.memory_enabled", return_value=True)
@patch("src.main.build_memory_db_path", return_value=":memory:")
@patch("src.main.init_memory_db", side_effect=RuntimeError("db init failed"))
def test_initialize_memory_is_best_effort_on_error(mock_init_db, mock_db_path, mock_enabled):
    from src.main import initialize_memory

    initialize_memory()


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
def test_digest_trigger_passes_schedule_payload(mock_run, client):
    mock_run.return_value = MagicMock(raw="digest posted", model="gemini/gemini-2.5-flash")
    response = client.post(
        "/digest/trigger",
        json={
            "run_source": "scheduled",
            "window_minutes": 60,
            "bucket_start_utc": "2026-02-28T11:00:00Z",
        },
    )
    assert response.status_code == 200
    mock_run.assert_called_once_with(
        window_minutes=60,
        run_source="scheduled",
        bucket_start_utc="2026-02-28T11:00:00Z",
    )


@patch("src.main.run_digest_crew")
def test_digest_trigger_requires_valid_token_when_configured(mock_run, client, monkeypatch):
    monkeypatch.setenv("LEADSYNC_TRIGGER_TOKEN", "secret-token")
    response = client.post("/digest/trigger")
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]
    mock_run.assert_not_called()


@patch("src.main.run_digest_crew")
def test_digest_trigger_accepts_valid_token_when_configured(mock_run, client, monkeypatch):
    monkeypatch.setenv("LEADSYNC_TRIGGER_TOKEN", "secret-token")
    mock_run.return_value = MagicMock(raw="digest posted", model="gemini/gemini-2.5-flash")
    response = client.post(
        "/digest/trigger",
        headers={"X-LeadSync-Trigger-Token": "secret-token"},
    )
    assert response.status_code == 200
    assert response.json()["result"] == "digest posted"
    mock_run.assert_called_once()


@patch("src.main.run_digest_crew")
def test_digest_trigger_rejects_invalid_window_minutes(mock_run, client):
    response = client.post("/digest/trigger", json={"window_minutes": 0})
    assert response.status_code == 400
    assert "window_minutes" in response.json()["detail"]
    mock_run.assert_not_called()


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

def test_slack_prefs_returns_410_deprecated(client):
    response = client.post(
        "/slack/prefs",
        content=b"text=add+Always+use+async",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 410
    assert "Google Docs" in response.json()["detail"]


def test_slack_prefs_ssl_check_returns_ok(client):
    response = client.post(
        "/slack/prefs",
        content=b"ssl_check=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
