"""Workflow 1 Jira tool bootstrap helpers."""

from typing import Any

from src.shared import build_tools, composio_user_id
from src.tools.tool_registry import WF1_JIRA_TOOLS


def get_agent_tools() -> list[Any]:
    """Return Workflow 1 tool list with explicit required Jira actions."""
    return build_tools(
        user_id=composio_user_id(),
        tools=WF1_JIRA_TOOLS,
    )
