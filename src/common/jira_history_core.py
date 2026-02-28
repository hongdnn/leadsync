"""Core Jira history lookup/query helpers used by Workflow 1 and 3."""

import logging
from typing import Any

from src.common.jira_history_parse import (
    extract_primary_component,
    parse_history_tickets,
    safe_dict,
    safe_list,
)
from src.common.tool_helpers import find_tool_by_name

logger = logging.getLogger(__name__)

GET_ISSUE_TOOL = "JIRA_GET_ISSUE"
SEARCH_ISSUES_TOOL = "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST"
DEFAULT_HISTORY_LIMIT = 10


def extract_primary_label(labels: list[Any]) -> str:
    """Return first non-empty Jira label string."""
    for label in labels:
        if isinstance(label, str) and label.strip():
            return label.strip()
    return ""


def escape_jql_value(value: str) -> str:
    """Escape string for simple JQL value interpolation."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_same_label_done_jql(
    project_key: str,
    label: str,
    exclude_issue_key: str,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> str:
    """Build JQL selecting completed same-label issues by resolution recency."""
    del limit
    project = escape_jql_value(project_key)
    label_value = escape_jql_value(label)
    exclude = escape_jql_value(exclude_issue_key)
    return (
        f'project = "{project}" '
        f'AND labels = "{label_value}" '
        "AND statusCategory = Done "
        f'AND key != "{exclude}" '
        "ORDER BY resolutiondate DESC"
    )


def load_issue_project_label_component(tools: list[Any], issue_key: str) -> tuple[str, str, str]:
    """Load current issue project key, primary label, and primary component."""
    issue_tool = find_tool_by_name(tools, GET_ISSUE_TOOL)
    if issue_tool is None or not issue_key:
        return "", "", ""
    try:
        result = issue_tool.run(issue_key=issue_key, fields=["project", "labels", "components"])
    except Exception:
        logger.exception("Failed to fetch Jira issue metadata for '%s'.", issue_key)
        return "", "", ""
    payload = safe_dict(result)
    issue = safe_dict(payload.get("issue")) if "issue" in payload else payload
    fields = safe_dict(issue.get("fields"))
    project = safe_dict(fields.get("project"))
    labels = safe_list(fields.get("labels"))
    components = safe_list(fields.get("components"))
    return (
        str(project.get("key", "")).strip(),
        extract_primary_label(labels),
        extract_primary_component(components),
    )


def load_issue_project_and_label(tools: list[Any], issue_key: str) -> tuple[str, str]:
    """Load current issue project key and primary label."""
    project_key, label, _component = load_issue_project_label_component(tools, issue_key)
    return project_key, label


def build_same_label_progress_context(
    tools: list[Any],
    project_key: str,
    label: str,
    exclude_issue_key: str,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> str:
    """Build formatted same-label done-ticket context for prompt injection."""
    if not project_key or not label:
        return "No comparable label history available."
    search_tool = find_tool_by_name(tools, SEARCH_ISSUES_TOOL)
    if search_tool is None:
        return "History retrieval unavailable: JIRA search tool unavailable."
    jql = build_same_label_done_jql(project_key, label, exclude_issue_key, limit=limit)
    try:
        result = search_tool.run(
            jql=jql,
            max_results=limit,
            fields=["summary", "description", "status", "resolutiondate", "labels"],
        )
    except Exception as exc:
        logger.exception("Failed to fetch same-label ticket history for '%s'.", exclude_issue_key)
        return f"History retrieval unavailable: {exc}"
    tickets = parse_history_tickets(result=result, limit=limit)
    if not tickets:
        return "No completed same-label tickets found."
    lines = [f"Same-label completed tickets (latest {len(tickets)}):"]
    for ticket in tickets:
        resolved = ticket.resolution_date or "unknown-resolution-date"
        summary = ticket.summary or "No summary"
        lines.append(
            f"- {ticket.key} [{ticket.status}] ({resolved}): {summary} | "
            f"Completed details: {ticket.description_excerpt}"
        )
    return "\n".join(lines)
