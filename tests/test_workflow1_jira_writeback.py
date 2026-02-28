"""Unit tests for deterministic Workflow 1 Jira write-back helpers."""

import logging
from unittest.mock import MagicMock

import pytest

from src.workflow1.jira_writeback import (
    apply_jira_writeback,
    build_comment_text,
    build_description_text,
)
from src.workflow1.prompt_artifact import upload_prompt_to_jira


def _tool(name: str, response: object | None = None) -> MagicMock:
    """Build a named tool mock with configurable run response."""
    tool = MagicMock()
    tool.name = name
    tool.run.return_value = {"successful": True} if response is None else response
    return tool


def test_apply_jira_writeback_calls_edit_and_comment_with_issue_key():
    edit_tool = _tool("JIRA_EDIT_ISSUE")
    comment_tool = _tool("JIRA_ADD_COMMENT")
    apply_jira_writeback(
        tools=[edit_tool, comment_tool],
        issue_key="LEADS-42",
        comment_text="Comment body",
        description_text="Description body",
        logger=logging.getLogger(__name__),
    )
    assert edit_tool.run.called
    assert comment_tool.run.called
    assert edit_tool.run.call_args.kwargs["issue_id_or_key"] == "LEADS-42"
    assert comment_tool.run.call_args.kwargs["issue_id_or_key"] == "LEADS-42"


def test_apply_jira_writeback_raises_on_failed_tool_response():
    edit_tool = _tool("JIRA_EDIT_ISSUE", response={"successful": False, "error": "Forbidden"})
    with pytest.raises(RuntimeError, match="JIRA_EDIT_ISSUE failed"):
        apply_jira_writeback(
            tools=[edit_tool],
            issue_key="LEADS-42",
            comment_text="Comment body",
            description_text="Description body",
            logger=logging.getLogger(__name__),
        )


def test_upload_prompt_to_jira_raises_when_tool_response_signals_failure():
    attachment_tool = _tool(
        "JIRA_ADD_ATTACHMENT",
        response={"successful": False, "error": "Issue not found"},
    )
    with pytest.raises(RuntimeError, match="JIRA_ADD_ATTACHMENT failed"):
        upload_prompt_to_jira(
            tools=[attachment_tool],
            issue_key="LEADS-42",
            markdown="## Task\nBody\n",
        )


def test_writeback_text_builders_include_expected_sections():
    comment = build_comment_text(
        issue_key="LEADS-42",
        summary="Implement OAuth",
        same_label_history="Same-label completed tickets:\n- LEADS-12 done",
        key_files_markdown="- `src/auth/service.py` - OAuth orchestration (confidence: high)",
        repo_owner="acme",
        repo_name="leadsync",
    )
    description = build_description_text(
        issue_key="LEADS-42",
        summary="Implement OAuth",
        prompt_markdown=(
            "## Constraints\n- Keep existing auth flow.\n"
            "## Implementation Rules\n- Add tests.\n"
            "## Expected Output\n- Updated endpoints.\n"
        ),
        key_files_markdown="- `src/auth/service.py` - OAuth orchestration (confidence: high)",
        repo_owner="acme",
        repo_name="leadsync",
    )
    assert "Previous same-label progress:" in comment
    assert "Recommended implementation path for current task:" in comment
    assert "Key files to inspect first:" in description
    assert "Implementation rules:" not in description
    assert "attached prompt file" in description
