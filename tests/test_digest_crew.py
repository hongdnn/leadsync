"""
tests/test_digest_crew.py
Unit tests for src/digest_crew.py — Workflow 2: End-of-Day Digest.
"""

import pytest
from unittest.mock import MagicMock, patch


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
