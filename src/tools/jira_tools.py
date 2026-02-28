"""Workflow 1 Jira tool bootstrap helpers."""

from typing import Any

from src.shared import build_tools, composio_user_id

REQUIRED_JIRA_TOOLS = [
    "JIRA_GET_ISSUE",
    "JIRA_EDIT_ISSUE",
    "JIRA_ADD_COMMENT",
    "JIRA_ADD_ATTACHMENT",
    "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST",
]


def get_agent_tools() -> list[Any]:
    """Return Workflow 1 tool list with explicit required Jira actions."""
    return build_tools(
        user_id=composio_user_id(),
        tools=REQUIRED_JIRA_TOOLS,
    )
