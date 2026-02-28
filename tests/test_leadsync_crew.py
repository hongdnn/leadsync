"""
tests/test_leadsync_crew.py
Unit tests for src/leadsync_crew.py — Workflow 1: Ticket Enrichment.
"""

import pytest
from unittest.mock import MagicMock, patch


SAMPLE_PAYLOAD = {
    "issue": {
        "key": "LEADS-1",
        "fields": {
            "summary": "Add login endpoint",
            "labels": ["backend"],
            "assignee": {"displayName": "Alice"},
            "project": {"key": "LEADS"},
            "components": [{"name": "auth"}],
        },
    }
}


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
def test_run_leadsync_crew_returns_crew_run_result(
    mock_crew_cls, mock_config, mock_get_tools, mock_agent_cls, mock_task_cls
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_env.return_value = "fake-key"
    mock_get_tools.return_value = []

    mock_kickoff_result = MagicMock()
    mock_kickoff_result.__str__ = lambda self: "enrichment done"
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = mock_kickoff_result
    mock_crew_cls.return_value = mock_crew_instance

    from src.leadsync_crew import run_leadsync_crew
    from src.shared import CrewRunResult
    result = run_leadsync_crew(payload=SAMPLE_PAYLOAD)

    assert isinstance(result, CrewRunResult)
    assert result.model == "gemini/gemini-2.5-flash"
    mock_crew_instance.kickoff.assert_called_once()


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
def test_run_leadsync_crew_model_fallback(
    mock_crew_cls, mock_config, mock_get_tools, mock_agent_cls, mock_task_cls
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash-latest"
    mock_config.require_env.return_value = "fake-key"
    mock_get_tools.return_value = []

    mock_kickoff_result = MagicMock()
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.side_effect = [
        Exception("Model NOT_FOUND"),
        mock_kickoff_result,
    ]
    mock_crew_cls.return_value = mock_crew_instance

    from src.leadsync_crew import run_leadsync_crew
    result = run_leadsync_crew(payload=SAMPLE_PAYLOAD)

    assert "latest" not in result.model
    assert mock_crew_instance.kickoff.call_count == 2


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
def test_run_leadsync_crew_uses_frontend_label(
    mock_crew_cls, mock_config, mock_get_tools, mock_agent_cls, mock_task_cls
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_env.return_value = "fake-key"
    mock_get_tools.return_value = []
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock()
    mock_crew_cls.return_value = mock_crew_instance

    payload = {
        "issue": {
            "key": "LEADS-2",
            "fields": {
                "summary": "Add button",
                "labels": ["frontend"],
                "assignee": {"displayName": "Bob"},
                "project": {"key": "LEADS"},
                "components": [],
            },
        }
    }

    from src.leadsync_crew import run_leadsync_crew
    result = run_leadsync_crew(payload=payload)

    assert result.model == "gemini/gemini-2.5-flash"
    mock_crew_instance.kickoff.assert_called_once()


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
def test_run_leadsync_crew_empty_payload_defaults(
    mock_crew_cls, mock_config, mock_get_tools, mock_agent_cls, mock_task_cls
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_env.return_value = "fake-key"
    mock_get_tools.return_value = []
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock()
    mock_crew_cls.return_value = mock_crew_instance

    from src.leadsync_crew import run_leadsync_crew
    result = run_leadsync_crew(payload={})

    assert result.model == "gemini/gemini-2.5-flash"
    mock_crew_instance.kickoff.assert_called_once()
