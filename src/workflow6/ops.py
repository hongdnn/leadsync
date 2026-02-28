"""
Workflow 6 — Composio tool operations: Jira implementation-scan comment.
Exports: post_done_scan_comment
"""

import logging
import re
from typing import Any

from src.common.tool_helpers import find_tool_by_name
from src.common.tool_response import response_indicates_failure, summarize_tool_response

logger = logging.getLogger(__name__)

DEDUP_MARKER = "Implementation Scan Complete"

_IMPL_SUMMARY_RE = re.compile(
    r"IMPLEMENTATION_SUMMARY:\s*(.+)", re.IGNORECASE
)
_FILES_CHANGED_RE = re.compile(
    r"FILES_CHANGED:\s*(.+)", re.IGNORECASE
)


def _run_required_tool(tool: Any, action: str, **kwargs: Any) -> Any:
    """Run a tool and raise RuntimeError when response indicates failure."""
    response = tool.run(**kwargs)
    if response_indicates_failure(response):
        details = summarize_tool_response(response)
        raise RuntimeError(f"{action} failed: {details}")
    return response


def _build_done_scan_comment(
    *,
    issue_key: str,
    ticket_summary: str,
    summary_text: str,
) -> str:
    """Build a plain text Jira comment from the summarizer agent output.

    Args:
        issue_key: Jira issue key (e.g. LEADS-99).
        ticket_summary: Ticket title/summary from Jira.
        summary_text: Raw summarizer agent output.
    Returns:
        Formatted plain text comment.
    """
    impl_match = _IMPL_SUMMARY_RE.search(summary_text)
    files_match = _FILES_CHANGED_RE.search(summary_text)

    impl = impl_match.group(1).strip() if impl_match else summary_text.strip()
    files = files_match.group(1).strip() if files_match else ""

    lines = [f"{DEDUP_MARKER} — {issue_key}"]
    if ticket_summary:
        lines.append(f"Ticket: {ticket_summary}")
    lines.append("")
    lines.append(f"Summary: {impl}")
    if files and files.lower() != "none":
        lines.append(f"Files Changed: {files}")
    lines.append("")
    lines.append("— Scanned by LeadSync")
    return "\n".join(lines)


def post_done_scan_comment(
    *,
    jira_tools: list[Any],
    issue_key: str,
    summary_text: str,
    ticket_summary: str = "",
) -> str:
    """Post an implementation scan summary as a Jira comment with idempotency.

    Args:
        jira_tools: Composio Jira tool list.
        issue_key: Jira issue key (e.g. LEADS-99).
        summary_text: Implementation summary produced by the summarizer agent.
        ticket_summary: Ticket title/summary from Jira.
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
            resp_str = str(response)
            if DEDUP_MARKER in resp_str and issue_key in resp_str:
                return "skipped:duplicate"
        except Exception:
            logger.warning(
                "WF6: JIRA_GET_ISSUE check failed for %s; proceeding.", issue_key
            )

    body = _build_done_scan_comment(
        issue_key=issue_key,
        ticket_summary=ticket_summary,
        summary_text=summary_text,
    )
    _run_required_tool(
        comment_tool, "JIRA_ADD_COMMENT", issue_id_or_key=issue_key, comment=body
    )
    return "posted"
