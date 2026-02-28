"""
src/workflow5/runner.py
Workflow 5: Jira PR Auto-Link rule engine.
Exports: run_workflow5(payload, github_tools, jira_tools) -> CrewRunResult
"""

import logging
from typing import Any

from src.shared import CrewRunResult
from src.workflow4.parsing import parse_pr_context
from src.workflow5.ops import (
    post_jira_pr_link_comment,
    transition_jira_to_in_review,
    post_github_no_ticket_warning,
)

ACTIONS_TO_PROCESS = {"opened", "reopened"}
MODEL = "rule-engine"
logger = logging.getLogger(__name__)


def run_workflow5(
    payload: dict[str, Any],
    github_tools: list[Any],
    jira_tools: list[Any],
) -> CrewRunResult:
    """Run Jira-GitHub PR auto-link rule engine.

    Args:
        payload: GitHub webhook JSON body.
        github_tools: Composio GitHub tools.
        jira_tools: Composio Jira tools.
    Returns:
        CrewRunResult with outcome summary and model='rule-engine'.
    """
    pr = parse_pr_context(payload)

    if pr.action not in ACTIONS_TO_PROCESS:
        return CrewRunResult(raw=f"skipped: action '{pr.action}'", model=MODEL)

    if not pr.number or not pr.owner or not pr.repo:
        return CrewRunResult(raw="skipped: missing PR metadata", model=MODEL)

    logger.warning(
        "Workflow5 run: action=%s pr=%s jira_key=%s",
        pr.action,
        pr.number,
        pr.jira_key or "N/A",
    )

    if pr.jira_key:
        comment_result = post_jira_pr_link_comment(
            jira_tools=jira_tools,
            ticket_key=pr.jira_key,
            pr_url=pr.html_url,
            pr_number=pr.number,
        )
        transition_result = transition_jira_to_in_review(
            jira_tools=jira_tools,
            ticket_key=pr.jira_key,
        )
        return CrewRunResult(
            raw=f"linked: PR #{pr.number} -> {pr.jira_key} comment={comment_result} transition={transition_result}",
            model=MODEL,
        )

    warning_result = post_github_no_ticket_warning(
        github_tools=github_tools,
        owner=pr.owner,
        repo=pr.repo,
        issue_number=pr.number,
    )
    return CrewRunResult(
        raw=f"warned: PR #{pr.number} has no Jira key; comment={warning_result}",
        model=MODEL,
    )
