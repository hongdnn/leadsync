"""
tests/test_slack_crew.py
Unit tests for src/slack_crew.py — Workflow 3: Slack Q&A.
"""

import pytest
from unittest.mock import MagicMock, patch


def test_parse_slack_text_splits_ticket_and_question():
    from src.slack_crew import parse_slack_text
    key, question = parse_slack_text("LEADS-123 What is the best approach?")
    assert key == "LEADS-123"
    assert question == "What is the best approach?"


def test_parse_slack_text_single_word_returns_empty_question():
    from src.slack_crew import parse_slack_text
    key, question = parse_slack_text("LEADS-42")
    assert key == "LEADS-42"
    assert question == ""


@patch("src.slack_crew.build_tools")
@patch("src.slack_crew.build_llm")
@patch("src.slack_crew.Crew")
def test_run_slack_crew_returns_crew_run_result(
    mock_crew_cls, mock_build_llm, mock_build_tools, monkeypatch, tmp_path
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")

    ctx_file = tmp_path / "tech-lead-context.md"
    ctx_file.write_text("# Tech Lead Context\nPrefer async.")

    mock_build_llm.return_value = "gemini/gemini-2.5-flash"
    mock_build_tools.return_value = []

    mock_kickoff_result = MagicMock()
    mock_kickoff_result.__str__ = lambda self: "Threaded reply posted."
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = mock_kickoff_result
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.slack_crew.TECH_LEAD_CONTEXT_PATH", str(ctx_file)):
        from src.slack_crew import run_slack_crew
        from src.shared import CrewRunResult
        result = run_slack_crew(ticket_key="LEADS-1", question="Use async?")

    assert isinstance(result, CrewRunResult)
    assert result.model == "gemini/gemini-2.5-flash"
    mock_crew_instance.kickoff.assert_called_once()


@patch("src.slack_crew.build_tools")
@patch("src.slack_crew.build_llm")
@patch("src.slack_crew.Crew")
def test_run_slack_crew_model_fallback(
    mock_crew_cls, mock_build_llm, mock_build_tools, monkeypatch, tmp_path
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")

    ctx_file = tmp_path / "tech-lead-context.md"
    ctx_file.write_text("# Tech Lead Context")

    mock_build_llm.return_value = "gemini/gemini-2.5-flash-latest"
    mock_build_tools.return_value = []

    mock_kickoff_result = MagicMock()
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.side_effect = [
        Exception("Model NOT_FOUND"),
        mock_kickoff_result,
    ]
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.slack_crew.TECH_LEAD_CONTEXT_PATH", str(ctx_file)):
        from src.slack_crew import run_slack_crew
        result = run_slack_crew(ticket_key="LEADS-1", question="Any concerns?")

    assert "latest" not in result.model
    assert mock_crew_instance.kickoff.call_count == 2


def test_run_slack_crew_raises_on_missing_slack_channel(monkeypatch, tmp_path):
    monkeypatch.delenv("SLACK_CHANNEL_ID", raising=False)
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")

    ctx_file = tmp_path / "tech-lead-context.md"
    ctx_file.write_text("# Tech Lead Context")

    with patch("src.slack_crew.TECH_LEAD_CONTEXT_PATH", str(ctx_file)):
        with patch("src.slack_crew.build_tools", return_value=[]):
            with patch("src.slack_crew.build_llm", return_value="gemini/gemini-2.5-flash"):
                from src.slack_crew import run_slack_crew
                with pytest.raises(RuntimeError, match="SLACK_CHANNEL_ID"):
                    run_slack_crew(ticket_key="LEADS-1", question="Any concerns?")
