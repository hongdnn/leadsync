"""
Workflow 6 — Composio tool operations: Jira implementation-scan comment.
Exports: post_done_scan_comment
"""

import logging
from typing import Any

from src.common.tool_helpers import find_tool_by_name
from src.common.tool_response import response_indicates_failure, summarize_tool_response

logger = logging.getLogger(__name__)

JIRA_COMMENT_MARKER = "<!-- leadsync:wf6 -->"


def _run_required_tool(tool: Any, action: str, **kwargs: Any) -> Any:
    """Run a tool and raise RuntimeError when response indicates failure."""
    response = tool.run(**kwargs)
    if response_indicates_failure(response):
        details = summarize_tool_response(response)
        raise RuntimeError(f"{action} failed: {details}")
    return response


def post_done_scan_comment(
    *,
    jira_tools: list[Any],
    issue_key: str,
    summary_text: str,
) -> str:
    """Post an implementation scan summary as a Jira comment with idempotency.

    Args:
        jira_tools: Composio Jira tool list.
        issue_key: Jira issue key (e.g. LEADS-99).
        summary_text: Implementation summary produced by the summarizer agent.
    Returns:
        'posted', 'skipped:duplicate', or 'skipped:no-tool'.
    """
    comment_tool = find_tool_by_name(jira_tools, "JIRA_ADD_COMMENT")
    if comment_tool is None:
        return "skipped:no-tool"

    get_tool = find_tool_by_name(jira_tools, "JIRA_GET_ISSUE")
    if get_tool is not None:
        try:
            response = get_tool.run(issue_id_or_key=issue_key)
            if JIRA_COMMENT_MARKER in str(response):
                return "skipped:duplicate"
        except Exception:
            logger.warning(
                "WF6: JIRA_GET_ISSUE check failed for %s; proceeding.", issue_key
            )

    body = (
        f"{JIRA_COMMENT_MARKER}\n"
        f"Implementation scan for {issue_key}:\n"
        f"{summary_text}"
    )
    _run_required_tool(
        comment_tool, "JIRA_ADD_COMMENT", issue_id_or_key=issue_key, comment=body
    )
    return "posted"
