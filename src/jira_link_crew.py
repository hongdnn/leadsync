"""
src/jira_link_crew.py
Workflow 5 — Jira-GitHub PR auto-link public wrapper.
Exports: run_jira_link_crew(payload) -> CrewRunResult
"""

from typing import Any

from src.shared import CrewRunResult, build_tools, composio_user_id
from src.tools.tool_registry import WF5_GITHUB_TOOLS, WF5_JIRA_TOOLS
from src.workflow5.runner import run_workflow5


def run_jira_link_crew(payload: dict[str, Any]) -> CrewRunResult:
    """Run Jira-GitHub PR auto-link from webhook payload.

    Args:
        payload: GitHub webhook JSON body.
    Returns:
        CrewRunResult with outcome summary.
    """
    user_id = composio_user_id()
    jira_tools = build_tools(user_id=user_id, tools=WF5_JIRA_TOOLS)
    github_tools = build_tools(user_id=user_id, tools=WF5_GITHUB_TOOLS)
    return run_workflow5(payload=payload, github_tools=github_tools, jira_tools=jira_tools)
