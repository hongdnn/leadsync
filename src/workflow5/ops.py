"""
src/workflow5/ops.py
Workflow 5 — Composio tool operations: Jira comment, status transition, GitHub warning.
Exports: post_jira_pr_link_comment, transition_jira_to_in_review, post_github_no_ticket_warning
"""

import logging
from typing import Any

from src.common.tool_helpers import find_tool_by_name
from src.common.tool_response import response_indicates_failure, summarize_tool_response

logger = logging.getLogger(__name__)



def _run_required_tool(tool: Any, action: str, **kwargs: Any) -> Any:
    """Run a tool and raise RuntimeError when response indicates failure."""
    response = tool.run(**kwargs)
    if response_indicates_failure(response):
        details = summarize_tool_response(response)
        raise RuntimeError(f"{action} failed: {details}")
    return response


def _build_pr_link_comment(
    *,
    pr_url: str,
    pr_number: int,
    pr_title: str = "",
    branch: str = "",
    owner: str = "",
    repo: str = "",
    head_sha: str = "",
) -> str:
    """Build a rich Jira comment body for a linked PR.

    Args:
        pr_url: Full GitHub PR URL.
        pr_number: PR number.
        pr_title: PR title text.
        branch: Source branch name.
        owner: Repository owner.
        repo: Repository name.
        head_sha: HEAD commit SHA.
    Returns:
        Formatted comment string with idempotency marker.
    """
    lines = [f"Pull Request #{pr_number} Linked"]
    if pr_title:
        lines.append(f"Title: {pr_title}")
    lines.append(f"URL: {pr_url}")
    if branch:
        lines.append(f"Branch: {branch}")
    if owner and repo:
        lines.append(f"Repository: {owner}/{repo}")
    if head_sha:
        lines.append(f"Commit: {head_sha[:7]}")
    lines.append("")
    lines.append("— Automatically linked by LeadSync")
    return "\n".join(lines)


def post_jira_pr_link_comment(
    *,
    jira_tools: list[Any],
    ticket_key: str,
    pr_url: str,
    pr_number: int,
    pr_title: str = "",
    branch: str = "",
    owner: str = "",
    repo: str = "",
    head_sha: str = "",
) -> str:
    """Post a PR-link comment on the Jira ticket with idempotency check.

    Args:
        jira_tools: Composio Jira tool list.
        ticket_key: Jira issue key (e.g. LEADS-99).
        pr_url: Full GitHub PR URL.
        pr_number: PR number.
        pr_title: PR title text.
        branch: Source branch name.
        owner: Repository owner.
        repo: Repository name.
        head_sha: HEAD commit SHA.
    Returns:
        'posted', 'skipped:duplicate', or 'skipped:no-tool'.
    """
    comment_tool = find_tool_by_name(jira_tools, "JIRA_ADD_COMMENT")
    if comment_tool is None:
        return "skipped:no-tool"

    get_tool = find_tool_by_name(jira_tools, "JIRA_GET_ISSUE")
    if get_tool is not None:
        try:
            response = get_tool.run(issue_id_or_key=ticket_key)
            resp_str = str(response)
            if pr_url in resp_str:
                return "skipped:duplicate"
        except Exception:
            logger.warning("WF5: JIRA_GET_ISSUE check failed for %s; proceeding.", ticket_key)

    body = _build_pr_link_comment(
        pr_url=pr_url,
        pr_number=pr_number,
        pr_title=pr_title,
        branch=branch,
        owner=owner,
        repo=repo,
        head_sha=head_sha,
    )
    _run_required_tool(comment_tool, "JIRA_ADD_COMMENT", issue_id_or_key=ticket_key, comment=body)
    return "posted"


def transition_jira_to_in_review(
    *,
    jira_tools: list[Any],
    ticket_key: str,
) -> str:
    """Transition a Jira ticket to 'In Review' status.

    Args:
        jira_tools: Composio Jira tool list.
        ticket_key: Jira issue key.
    Returns:
        'transitioned:<name>', 'skipped:no-in-review-transition', or 'skipped:no-tool'.
    """
    transitions_tool = find_tool_by_name(jira_tools, "JIRA_GET_TRANSITIONS")
    if transitions_tool is None:
        return "skipped:no-tool"
    transition_tool = find_tool_by_name(jira_tools, "JIRA_TRANSITION_ISSUE")
    if transition_tool is None:
        return "skipped:no-tool"

    response = transitions_tool.run(issue_id_or_key=ticket_key)
    transitions: list[dict[str, Any]] = []
    if isinstance(response, dict):
        transitions = response.get("transitions", [])
    elif isinstance(response, list):
        transitions = response

    target_id: str | None = None
    target_name: str = ""
    for item in transitions:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        if "in review" in name.lower():
            target_id = str(item.get("id", ""))
            target_name = name
            break

    if not target_id:
        logger.warning("WF5: No 'In Review' transition found for %s.", ticket_key)
        return "skipped:no-in-review-transition"

    _run_required_tool(
        transition_tool,
        "JIRA_TRANSITION_ISSUE",
        issue_id_or_key=ticket_key,
        transition_id=target_id,
    )
    return f"transitioned:{target_name}"


def post_github_no_ticket_warning(
    *,
    github_tools: list[Any],
    owner: str,
    repo: str,
    issue_number: int,
) -> str:
    """Post a warning comment on GitHub PR when no Jira ticket is detected.

    Args:
        github_tools: Composio GitHub tool list.
        owner: Repository owner.
        repo: Repository name.
        issue_number: PR number (GitHub treats PRs as issues).
    Returns:
        'posted' or 'skipped:no-tool'.
    """
    tool = find_tool_by_name(github_tools, "GITHUB_CREATE_AN_ISSUE_COMMENT")
    if tool is None:
        return "skipped:no-tool"

    body = "No Jira ticket detected. Please add LEADS-XXX to the PR title."
    try:
        tool.run(owner=owner, repo=repo, issue_number=issue_number, body=body)
    except TypeError:
        tool.run(owner=owner, repo=repo, number=issue_number, body=body)
    return "posted"
