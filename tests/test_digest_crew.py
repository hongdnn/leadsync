"""
tests/test_digest_crew.py
Unit tests for src/digest_crew.py — Workflow 2: End-of-Day Digest.
"""

import pytest
from unittest.mock import MagicMock, patch


def test_parse_digest_areas_parses_structured_lines():
    from src.digest_crew import _parse_digest_areas

    digest_text = (
        "AREA: auth | SUMMARY: Added token refresh guard | RISKS: Needs load testing\n"
        "AREA: api | SUMMARY: Refactored webhook retries | RISKS: Verify idempotency"
    )
    rows = _parse_digest_areas(digest_text)
    assert rows == [
        ("auth", "Added token refresh guard", "Needs load testing"),
        ("api", "Refactored webhook retries", "Verify idempotency"),
    ]


@patch("src.digest_crew.Task")
@patch("src.digest_crew.Agent")
@patch("src.digest_crew.build_tools")
@patch("src.digest_crew.build_llm")
@patch("src.digest_crew.Crew")
def test_run_digest_crew_returns_crew_run_result(
    mock_crew_cls, mock_build_llm, mock_build_tools, mock_agent_cls, mock_task_cls, monkeypatch
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("LEADSYNC_GITHUB_REPO_OWNER", "acme")
    monkeypatch.setenv("LEADSYNC_GITHUB_REPO_NAME", "leadsync")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    mock_build_llm.return_value = "gemini/gemini-2.5-flash"
    mock_build_tools.return_value = []

    mock_kickoff_result = MagicMock()
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = mock_kickoff_result
    mock_crew_cls.return_value = mock_crew_instance

    from src.digest_crew import run_digest_crew
    from src.shared import CrewRunResult

    result = run_digest_crew()

    assert isinstance(result, CrewRunResult)
    assert result.model == "gemini/gemini-2.5-flash"
    mock_crew_instance.kickoff.assert_called_once()


@patch("src.digest_crew.Task")
@patch("src.digest_crew.Agent")
@patch("src.digest_crew.build_tools")
@patch("src.digest_crew.build_llm")
@patch("src.digest_crew.Crew")
def test_run_digest_crew_model_fallback(
    mock_crew_cls, mock_build_llm, mock_build_tools, mock_agent_cls, mock_task_cls, monkeypatch
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("LEADSYNC_GITHUB_REPO_OWNER", "acme")
    monkeypatch.setenv("LEADSYNC_GITHUB_REPO_NAME", "leadsync")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    mock_build_llm.return_value = "gemini/gemini-2.5-flash-latest"
    mock_build_tools.return_value = []

    mock_kickoff_result = MagicMock()
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.side_effect = [Exception("Model NOT_FOUND"), mock_kickoff_result]
    mock_crew_cls.return_value = mock_crew_instance

    from src.digest_crew import run_digest_crew

    result = run_digest_crew()

    assert "latest" not in result.model
    assert mock_crew_instance.kickoff.call_count == 2


def test_run_digest_crew_raises_when_missing_slack_channel(monkeypatch):
    monkeypatch.delenv("SLACK_CHANNEL_ID", raising=False)
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    with patch("src.digest_crew.build_tools", return_value=[]):
        with patch("src.digest_crew.build_llm", return_value="gemini/gemini-2.5-flash"):
            from src.digest_crew import run_digest_crew
            with pytest.raises(RuntimeError, match="SLACK_CHANNEL_ID"):
                run_digest_crew()


@patch("src.digest_crew.Task")
@patch("src.digest_crew.Agent")
@patch("src.digest_crew.build_tools")
@patch("src.digest_crew.build_llm")
@patch("src.digest_crew.Crew")
def test_run_digest_crew_records_memory_when_enabled(
    mock_crew_cls, mock_build_llm, mock_build_tools, mock_agent_cls, mock_task_cls, monkeypatch
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("LEADSYNC_GITHUB_REPO_OWNER", "acme")
    monkeypatch.setenv("LEADSYNC_GITHUB_REPO_NAME", "leadsync")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    mock_build_llm.return_value = "gemini/gemini-2.5-flash"
    mock_build_tools.return_value = []
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock()
    mock_crew_cls.return_value = mock_crew_instance
    scan_task = MagicMock()
    scan_task.output = MagicMock(raw="Auth commits")
    write_task = MagicMock()
    write_task.output = MagicMock(
        raw="AREA: auth | SUMMARY: Added token refresh | RISKS: Verify load"
    )
    post_task = MagicMock()
    mock_task_cls.side_effect = [scan_task, write_task, post_task]

    with patch("src.digest_crew.memory_enabled", return_value=True):
        with patch("src.digest_crew.build_memory_db_path", return_value=":memory:"):
            with patch("src.digest_crew.record_event") as mock_record_event:
                with patch("src.digest_crew.record_memory_item") as mock_record_item:
                    from src.digest_crew import run_digest_crew
                    run_digest_crew()

    assert mock_record_event.called
    assert mock_record_item.called


@patch("src.digest_crew.run_workflow2")
@patch("src.digest_crew.build_tools")
@patch("src.digest_crew.build_digest_window_minutes")
@patch("src.digest_crew.build_llm")
def test_run_digest_crew_passes_schedule_arguments(
    mock_build_llm,
    mock_build_window,
    mock_build_tools,
    mock_run_workflow2,
    monkeypatch,
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("LEADSYNC_GITHUB_REPO_OWNER", "acme")
    monkeypatch.setenv("LEADSYNC_GITHUB_REPO_NAME", "leadsync")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    mock_build_llm.return_value = "gemini/gemini-2.5-flash"
    mock_build_window.return_value = 60
    mock_build_tools.return_value = []
    mock_run_workflow2.return_value = MagicMock(raw="ok", model="gemini/gemini-2.5-flash")

    from src.digest_crew import run_digest_crew

    run_digest_crew(
        window_minutes=120,
        run_source="scheduled",
        bucket_start_utc="2026-02-28T11:00:00Z",
        repo_owner="octocat",
        repo_name="hello-world",
    )

    kwargs = mock_run_workflow2.call_args.kwargs
    assert kwargs["window_minutes"] == 120
    assert kwargs["run_source"] == "scheduled"
    assert kwargs["bucket_start_utc"] == "2026-02-28T11:00:00Z"
    assert kwargs["repo_owner"] == "octocat"
    assert kwargs["repo_name"] == "hello-world"


def test_parse_digest_blocks_parses_new_multiline_format():
    from src.workflow2.parsing import parse_digest_areas, parse_digest_blocks

    digest_text = (
        "---\n"
        "AREA: WF2 Digest\n"
        "AUTHORS: ramis, john\n"
        "COMMITS: 2\n"
        "FILES: src/workflow2/runner.py (M), src/digest_crew.py (M)\n"
        "SUMMARY: Fixed WF2 digest by injecting since timestamp into GitHub Scanner.\n"
        "DECISIONS: Chose timestamp injection for accurate hourly window filtering.\n"
        "---\n"
        "AREA: Documentation\n"
        "AUTHORS: ramis\n"
        "COMMITS: 1\n"
        "FILES: CLAUDE.md (M)\n"
        "SUMMARY: Updated CLAUDE.md with tool usage limitations.\n"
        "DECISIONS: None.\n"
        "---"
    )
    # parse_digest_areas returns legacy-compatible tuples
    rows = parse_digest_areas(digest_text)
    assert len(rows) == 2
    assert rows[0][0] == "WF2 Digest"
    assert "timestamp" in rows[0][1]
    assert rows[1][0] == "Documentation"

    # parse_digest_blocks returns rich DigestArea objects
    blocks = parse_digest_blocks(digest_text)
    assert len(blocks) == 2
    assert blocks[0].authors == "ramis, john"
    assert blocks[0].commits == "2"
    assert "runner.py" in blocks[0].files
    assert blocks[1].authors == "ramis"
    assert blocks[1].commits == "1"


def test_parse_digest_blocks_falls_back_to_legacy_format():
    from src.workflow2.parsing import parse_digest_blocks

    digest_text = (
        "AREA: auth | SUMMARY: Added token refresh guard | RISKS: Needs load testing\n"
        "AREA: api | SUMMARY: Refactored webhook retries | RISKS: Verify idempotency"
    )
    blocks = parse_digest_blocks(digest_text)
    assert len(blocks) == 2
    assert blocks[0].area == "auth"
    assert blocks[0].summary == "Added token refresh guard"
    assert blocks[0].decisions == "Needs load testing"
    assert blocks[0].authors == ""  # legacy has no authors


def test_run_digest_crew_raises_when_missing_repo_target(monkeypatch):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.delenv("LEADSYNC_GITHUB_REPO_OWNER", raising=False)
    monkeypatch.delenv("LEADSYNC_GITHUB_REPO_NAME", raising=False)
    with patch("src.digest_crew.build_tools", return_value=[]):
        with patch("src.digest_crew.build_llm", return_value="gemini/gemini-2.5-flash"):
            from src.digest_crew import run_digest_crew
            with pytest.raises(RuntimeError, match="Missing GitHub repository target"):
                run_digest_crew()
