"""Workflow 4 wrapper for GitHub PR auto-details enrichment."""

from typing import Any

from src.shared import CrewRunResult, build_tools, composio_user_id
from src.workflow4.runner import run_workflow4


def run_pr_review_crew(payload: dict[str, Any]) -> CrewRunResult:
    """Run PR details generation from code changes."""
    user_id = composio_user_id()
    github_tools = build_tools(
        user_id=user_id,
        tools=[
            "GITHUB_LIST_PULL_REQUEST_FILES",
            "GITHUB_LIST_FILES_FOR_A_PULL_REQUEST",
            "GITHUB_LIST_FILES_ON_A_PULL_REQUEST",
            "GITHUB_UPDATE_A_PULL_REQUEST",
            "GITHUB_EDIT_A_PULL_REQUEST",
            "GITHUB_UPDATE_PULL_REQUEST",
        ],
    )
    jira_tools: list[Any] = []
    return run_workflow4(payload=payload, github_tools=github_tools, jira_tools=jira_tools)
