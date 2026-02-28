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


@patch("src.slack_crew.Task")
@patch("src.slack_crew.Agent")
@patch("src.slack_crew.build_tools")
@patch("src.slack_crew.build_llm")
@patch("src.slack_crew.Crew")
def test_run_slack_crew_returns_crew_run_result(
    mock_crew_cls, mock_build_llm, mock_build_tools, mock_agent_cls, mock_task_cls,
    monkeypatch
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    mock_build_llm.return_value = "gemini/gemini-2.5-flash"
    mock_build_tools.return_value = []

    mock_kickoff_result = MagicMock()
    mock_kickoff_result.__str__ = lambda self: "Threaded reply posted."
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = mock_kickoff_result
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.slack_crew.load_preferences", return_value="# Tech Lead Context\nPrefer async."):
        from src.slack_crew import run_slack_crew
        from src.shared import CrewRunResult
        result = run_slack_crew(ticket_key="LEADS-1", question="Use async?")

    assert isinstance(result, CrewRunResult)
    assert result.model == "gemini/gemini-2.5-flash"
    mock_crew_instance.kickoff.assert_called_once()


@patch("src.slack_crew.Task")
@patch("src.slack_crew.Agent")
@patch("src.slack_crew.build_tools")
@patch("src.slack_crew.build_llm")
@patch("src.slack_crew.Crew")
def test_run_slack_crew_model_fallback(
    mock_crew_cls, mock_build_llm, mock_build_tools, mock_agent_cls, mock_task_cls,
    monkeypatch
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    mock_build_llm.return_value = "gemini/gemini-2.5-flash-latest"
    mock_build_tools.return_value = []

    mock_kickoff_result = MagicMock()
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.side_effect = [
        Exception("Model NOT_FOUND"),
        mock_kickoff_result,
    ]
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.slack_crew.load_preferences", return_value="# Tech Lead Context\nPrefer async."):
        from src.slack_crew import run_slack_crew
        result = run_slack_crew(ticket_key="LEADS-1", question="Any concerns?")

    assert "latest" not in result.model
    assert mock_crew_instance.kickoff.call_count == 2


def test_run_slack_crew_raises_on_missing_slack_channel(monkeypatch):
    monkeypatch.delenv("SLACK_CHANNEL_ID", raising=False)
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    with patch("src.slack_crew.load_preferences", return_value="# Tech Lead Context\nPrefer async."):
        with patch("src.slack_crew.build_tools", return_value=[]):
            with patch("src.slack_crew.build_llm", return_value="gemini/gemini-2.5-flash"):
                from src.slack_crew import run_slack_crew
                with pytest.raises(RuntimeError, match="SLACK_CHANNEL_ID"):
                    run_slack_crew(ticket_key="LEADS-1", question="Any concerns?")


@patch("src.slack_crew.Task")
@patch("src.slack_crew.Agent")
@patch("src.slack_crew.build_tools")
@patch("src.slack_crew.build_llm")
@patch("src.slack_crew.Crew")
def test_retrieve_task_contains_classification_instructions(
    mock_crew_cls, mock_build_llm, mock_build_tools, mock_agent_cls, mock_task_cls,
    monkeypatch,
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    mock_build_llm.return_value = "gemini/gemini-2.5-flash"
    mock_build_tools.return_value = []
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock(__str__=lambda s: "done")
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.slack_crew.load_preferences", return_value="# Prefs"):
        from src.slack_crew import run_slack_crew
        run_slack_crew(ticket_key="LEADS-1", question="How should I implement this?")

    retrieve_call = mock_task_cls.call_args_list[0]
    desc = retrieve_call[1]["description"]
    assert "QUESTION_TYPE" in desc
    assert "PROGRESS" in desc
    assert "IMPLEMENTATION" in desc
    assert "GENERAL" in desc


@patch("src.slack_crew.Task")
@patch("src.slack_crew.Agent")
@patch("src.slack_crew.build_tools")
@patch("src.slack_crew.build_llm")
@patch("src.slack_crew.Crew")
def test_reason_task_contains_conditional_branches(
    mock_crew_cls, mock_build_llm, mock_build_tools, mock_agent_cls, mock_task_cls,
    monkeypatch,
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    mock_build_llm.return_value = "gemini/gemini-2.5-flash"
    mock_build_tools.return_value = []
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock(__str__=lambda s: "done")
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.slack_crew.load_preferences", return_value="# Prefs\n- Prefer async."):
        from src.slack_crew import run_slack_crew
        run_slack_crew(ticket_key="LEADS-1", question="Should I use a new table?")

    reason_call = mock_task_cls.call_args_list[1]
    desc = reason_call[1]["description"]
    assert "QUESTION_TYPE: PROGRESS" in desc
    assert "QUESTION_TYPE: GENERAL" in desc
    assert "QUESTION_TYPE: IMPLEMENTATION" in desc
    assert "Here is summary of previous progress related to tasks with the same label" in desc
    assert "ticket enriched" in desc
    assert "Do NOT reference or apply any tech lead preferences" in desc
    assert "Prefer async" in desc
