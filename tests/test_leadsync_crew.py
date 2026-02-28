"""
tests/test_leadsync_crew.py
Unit tests for src/leadsync_crew.py — Workflow 1: Ticket Enrichment.
"""

from pathlib import Path
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


def _attachment_tool() -> MagicMock:
    """Build a mock Jira attachment tool."""
    tool = MagicMock()
    tool.name = "JIRA_ADD_ATTACHMENT"
    return tool


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.build_tools", return_value=[])
@patch("src.leadsync_crew.load_preferences_for_category", return_value="# Prefs\n- Keep APIs thin.")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
@patch("src.leadsync_crew._attach_prompt_file")
@patch("src.leadsync_crew._write_prompt_file")
def test_run_leadsync_crew_returns_crew_run_result(
    mock_write_prompt,
    mock_attach_prompt,
    mock_crew_cls,
    mock_config,
    mock_load_prefs,
    mock_build_tools,
    mock_get_tools,
    mock_agent_cls,
    mock_task_cls,
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_gemini_api_key.return_value = "fake-key"
    mock_get_tools.return_value = []
    mock_write_prompt.return_value = Path("artifacts/workflow1/prompt-LEADS-1.md")

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
    mock_attach_prompt.assert_called_once()


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.build_tools", return_value=[])
@patch("src.leadsync_crew.load_preferences_for_category", return_value="# Prefs\n- Keep APIs thin.")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
@patch("src.leadsync_crew._attach_prompt_file")
@patch("src.leadsync_crew._write_prompt_file")
def test_run_leadsync_crew_model_fallback(
    mock_write_prompt,
    mock_attach_prompt,
    mock_crew_cls,
    mock_config,
    mock_load_prefs,
    mock_build_tools,
    mock_get_tools,
    mock_agent_cls,
    mock_task_cls,
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash-latest"
    mock_config.require_gemini_api_key.return_value = "fake-key"
    mock_get_tools.return_value = []
    mock_write_prompt.return_value = Path("artifacts/workflow1/prompt-LEADS-1.md")

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
    mock_attach_prompt.assert_called_once()


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.build_tools", return_value=[])
@patch("src.leadsync_crew.load_preferences_for_category", return_value="# Prefs\n- Keep APIs thin.")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
@patch("src.leadsync_crew._attach_prompt_file")
@patch("src.leadsync_crew._write_prompt_file")
def test_run_leadsync_crew_uses_frontend_label(
    mock_write_prompt,
    mock_attach_prompt,
    mock_crew_cls,
    mock_config,
    mock_load_prefs,
    mock_build_tools,
    mock_get_tools,
    mock_agent_cls,
    mock_task_cls,
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_gemini_api_key.return_value = "fake-key"
    mock_get_tools.return_value = []
    mock_write_prompt.return_value = Path("artifacts/workflow1/prompt-LEADS-2.md")
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
    mock_attach_prompt.assert_called_once()


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.build_tools", return_value=[])
@patch("src.leadsync_crew.load_preferences_for_category", return_value="# Prefs\n- Keep APIs thin.")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
@patch("src.leadsync_crew._attach_prompt_file")
@patch("src.leadsync_crew._write_prompt_file")
def test_run_leadsync_crew_empty_payload_defaults(
    mock_write_prompt,
    mock_attach_prompt,
    mock_crew_cls,
    mock_config,
    mock_load_prefs,
    mock_build_tools,
    mock_get_tools,
    mock_agent_cls,
    mock_task_cls,
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_gemini_api_key.return_value = "fake-key"
    mock_get_tools.return_value = []
    mock_write_prompt.return_value = Path("artifacts/workflow1/prompt-UNKNOWN.md")
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock()
    mock_crew_cls.return_value = mock_crew_instance

    from src.leadsync_crew import run_leadsync_crew
    result = run_leadsync_crew(payload={})

    assert result.model == "gemini/gemini-2.5-flash"
    mock_crew_instance.kickoff.assert_called_once()
    mock_attach_prompt.assert_called_once()


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.build_tools", return_value=[])
@patch(
    "src.leadsync_crew.load_preferences_for_category",
    side_effect=RuntimeError("Failed to fetch Google Docs preferences"),
)
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
def test_run_leadsync_crew_raises_when_google_doc_fetch_fails(
    mock_crew_cls,
    mock_config,
    mock_load_prefs,
    mock_build_tools,
    mock_get_tools,
    mock_agent_cls,
    mock_task_cls,
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_gemini_api_key.return_value = "fake-key"
    mock_get_tools.return_value = []

    from src.leadsync_crew import run_leadsync_crew
    with pytest.raises(RuntimeError, match="Google Docs preferences"):
        run_leadsync_crew(payload=SAMPLE_PAYLOAD)


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.build_tools", return_value=[])
@patch("src.leadsync_crew.load_preferences_for_category", return_value="# Prefs\n- Keep APIs thin.")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
def test_run_leadsync_crew_writes_required_prompt_sections_and_attaches(
    mock_crew_cls,
    mock_config,
    mock_load_prefs,
    mock_build_tools,
    mock_get_tools,
    mock_agent_cls,
    mock_task_cls,
    tmp_path,
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_gemini_api_key.return_value = "fake-key"
    attachment_tool = _attachment_tool()
    mock_get_tools.return_value = [attachment_tool]
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock()
    mock_crew_cls.return_value = mock_crew_instance

    gather_task = MagicMock()
    gather_task.output = MagicMock(raw="Existing context from linked tickets.")
    reason_task = MagicMock()
    reason_task.output = MagicMock(raw="Brief suggestion without required headings.")
    propagate_task = MagicMock()
    mock_task_cls.side_effect = [gather_task, reason_task, propagate_task]

    with patch("src.leadsync_crew.ARTIFACT_DIR", tmp_path):
        from src.leadsync_crew import run_leadsync_crew
        run_leadsync_crew(payload=SAMPLE_PAYLOAD)

    gather_desc = mock_task_cls.call_args_list[0][1]["description"]
    reason_desc = mock_task_cls.call_args_list[1][1]["description"]
    propagate_desc = mock_task_cls.call_args_list[2][1]["description"]
    assert "latest 10 completed same-label tickets" in gather_desc
    assert "source files or modules likely impacted" in gather_desc
    assert "same-label completed work" in reason_desc
    assert "Google Docs category" in reason_desc
    assert "technical execution guidance" in propagate_desc
    assert "without markdown syntax" in propagate_desc
    assert "This ticket" in propagate_desc

    prompt_file = tmp_path / "prompt-LEADS-1.md"
    assert prompt_file.exists()
    prompt_markdown = prompt_file.read_text(encoding="utf-8")
    assert "## Task" in prompt_markdown
    assert "## Context" in prompt_markdown
    assert "## Constraints" in prompt_markdown
    assert "## Implementation Rules" in prompt_markdown
    assert "## Expected Output" in prompt_markdown
    attachment_tool.run.assert_called_once()
    call_kwargs = attachment_tool.run.call_args.kwargs
    assert call_kwargs["issue_key"] == "LEADS-1"
    assert call_kwargs["local_file_path"] == str(prompt_file.resolve())
    assert call_kwargs["file_to_upload"] == str(prompt_file.resolve())


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.build_tools", return_value=[])
@patch("src.leadsync_crew.load_preferences_for_category", return_value="# Prefs\n- Keep APIs thin.")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
def test_run_leadsync_crew_missing_attachment_tool_raises(
    mock_crew_cls,
    mock_config,
    mock_load_prefs,
    mock_build_tools,
    mock_get_tools,
    mock_agent_cls,
    mock_task_cls,
    tmp_path,
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_gemini_api_key.return_value = "fake-key"
    mock_get_tools.return_value = []
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock()
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.leadsync_crew.ARTIFACT_DIR", tmp_path):
        from src.leadsync_crew import run_leadsync_crew
        with pytest.raises(RuntimeError, match="JIRA_ADD_ATTACHMENT"):
            run_leadsync_crew(payload=SAMPLE_PAYLOAD)


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.build_tools", return_value=[])
@patch("src.leadsync_crew.load_preferences_for_category", return_value="# Prefs\n- Keep APIs thin.")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
def test_run_leadsync_crew_attachment_tool_failure_raises(
    mock_crew_cls,
    mock_config,
    mock_load_prefs,
    mock_build_tools,
    mock_get_tools,
    mock_agent_cls,
    mock_task_cls,
    tmp_path,
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_gemini_api_key.return_value = "fake-key"
    attachment_tool = _attachment_tool()
    attachment_tool.run.side_effect = Exception("attachment failed")
    mock_get_tools.return_value = [attachment_tool]
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock()
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.leadsync_crew.ARTIFACT_DIR", tmp_path):
        from src.leadsync_crew import run_leadsync_crew
        with pytest.raises(Exception, match="attachment failed"):
            run_leadsync_crew(payload=SAMPLE_PAYLOAD)


def test_select_ruleset_file_prefers_matching_label():
    from src.leadsync_crew import _select_ruleset_file

    selected = _select_ruleset_file(labels=["frontend", "backend"], component_names=[])
    assert selected == "frontend-ruleset.md"


def test_select_ruleset_file_supports_synonym_labels():
    from src.leadsync_crew import _select_ruleset_file

    selected = _select_ruleset_file(labels=["db-migration"], component_names=[])
    assert selected == "db-ruleset.md"


def test_select_ruleset_file_uses_component_fallback():
    from src.leadsync_crew import _select_ruleset_file

    selected = _select_ruleset_file(labels=[], component_names=["ui"])
    assert selected == "frontend-ruleset.md"


def test_select_ruleset_file_defaults_to_backend():
    from src.leadsync_crew import _select_ruleset_file

    selected = _select_ruleset_file(labels=["priority-high"], component_names=["ops"])
    assert selected == "backend-ruleset.md"


@patch("src.leadsync_crew.Task")
@patch("src.leadsync_crew.Agent")
@patch("src.leadsync_crew.get_agent_tools")
@patch("src.leadsync_crew.build_tools", return_value=[])
@patch("src.leadsync_crew.load_preferences_for_category", return_value="# Prefs\n- Keep APIs thin.")
@patch("src.leadsync_crew.Config")
@patch("src.leadsync_crew.Crew")
def test_run_leadsync_crew_records_memory_when_enabled(
    mock_crew_cls,
    mock_config,
    mock_load_prefs,
    mock_build_tools,
    mock_get_tools,
    mock_agent_cls,
    mock_task_cls,
    tmp_path,
):
    mock_config.get_gemini_model.return_value = "gemini/gemini-2.5-flash"
    mock_config.require_gemini_api_key.return_value = "fake-key"
    attachment_tool = _attachment_tool()
    mock_get_tools.return_value = [attachment_tool]
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock()
    mock_crew_cls.return_value = mock_crew_instance
    gather_task = MagicMock()
    gather_task.output = MagicMock(raw="Gathered context")
    reason_task = MagicMock()
    reason_task.output = MagicMock(raw="Reasoned output")
    propagate_task = MagicMock()
    mock_task_cls.side_effect = [gather_task, reason_task, propagate_task]

    with patch("src.leadsync_crew.memory_enabled", return_value=True):
        with patch("src.leadsync_crew.build_memory_db_path", return_value=":memory:"):
            with patch("src.leadsync_crew.record_event") as mock_record_event:
                with patch("src.leadsync_crew.record_memory_item") as mock_record_item:
                    with patch("src.leadsync_crew.ARTIFACT_DIR", tmp_path):
                        from src.leadsync_crew import run_leadsync_crew
                        run_leadsync_crew(payload=SAMPLE_PAYLOAD)

    assert mock_record_event.called
    assert mock_record_item.called
