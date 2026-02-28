"""Workflow 4 wrapper for GitHub PR auto-details enrichment."""

from typing import Any

from src.shared import CrewRunResult, build_tools, composio_user_id
from src.tools.tool_registry import WF4_GITHUB_TOOLS
from src.workflow4.runner import run_workflow4


def run_pr_review_crew(payload: dict[str, Any]) -> CrewRunResult:
    """Run PR details generation from code changes."""
    user_id = composio_user_id()
    github_tools = build_tools(user_id=user_id, tools=WF4_GITHUB_TOOLS)
    jira_tools: list[Any] = []
    return run_workflow4(payload=payload, github_tools=github_tools, jira_tools=jira_tools)
