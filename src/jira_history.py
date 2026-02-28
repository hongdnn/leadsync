"""Shared Jira history helpers for same-label completed ticket context."""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)
_GET_ISSUE_TOOL = "JIRA_GET_ISSUE"
_SEARCH_ISSUES_TOOL = "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST"
DEFAULT_HISTORY_LIMIT = 10

@dataclass
class HistoryTicket:
    """Compact shape for prior completed Jira ticket context."""

    key: str
    summary: str
    description_excerpt: str
    status: str
    resolution_date: str

def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace into single spaces."""
    return " ".join(text.split())


def _extract_text_from_adf(value: Any) -> str:
    """
    Extract plain text from common Jira ADF-like structures.

    Args:
        value: Jira description field value.
    Returns:
        Flattened plain text when possible.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [_extract_text_from_adf(item) for item in value]
        return " ".join(part for part in parts if part.strip())
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text
        content = value.get("content")
        return _extract_text_from_adf(content)
    return ""


def _description_excerpt(value: Any, max_chars: int = 220) -> str:
    """
    Convert Jira description payload into a short excerpt.

    Args:
        value: Jira description field value.
        max_chars: Maximum excerpt length.
    Returns:
        Single-line excerpt for prompt context.
    """
    plain = _normalize_whitespace(_extract_text_from_adf(value))
    if not plain:
        return "No implementation notes provided."
    if len(plain) <= max_chars:
        return plain
    return plain[: max_chars - 3].rstrip() + "..."


def _find_tool(tools: list[Any], name: str) -> Any | None:
    expected = name.upper()
    for tool in tools:
        if getattr(tool, "name", "").upper() == expected:
            return tool
    return None


def extract_primary_label(labels: list[Any]) -> str:
    """Return the first non-empty Jira label."""
    for label in labels:
        if isinstance(label, str) and label.strip():
            return label.strip()
    return ""


def _escape_jql_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_same_label_done_jql(
    project_key: str, label: str, exclude_issue_key: str, limit: int = DEFAULT_HISTORY_LIMIT
) -> str:
    """
    Build bounded JQL for same-label completed issues ordered by recency.

    Args:
        project_key: Jira project key.
        label: Jira label to match.
        exclude_issue_key: Current issue to exclude.
        limit: Included for interface consistency; enforced via max_results.
    Returns:
        JQL string.
    """
    del limit
    project = _escape_jql_value(project_key)
    label_value = _escape_jql_value(label)
    exclude = _escape_jql_value(exclude_issue_key)
    return (
        f'project = "{project}" '
        f'AND labels = "{label_value}" '
        "AND statusCategory = Done "
        f'AND key != "{exclude}" '
        "ORDER BY resolutiondate DESC"
    )


def _extract_issue_list(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    payload = _safe_dict(result)
    for key in ("issues", "data", "result", "response"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        nested = _safe_dict(candidate).get("issues")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return []


def _parse_history_tickets(result: Any, limit: int) -> list[HistoryTicket]:
    tickets: list[HistoryTicket] = []
    for issue in _extract_issue_list(result):
        fields = _safe_dict(issue.get("fields"))
        status = _safe_dict(fields.get("status")).get("name", "Done")
        tickets.append(
            HistoryTicket(
                key=str(issue.get("key", "")),
                summary=str(fields.get("summary", "")).strip(),
                description_excerpt=_description_excerpt(fields.get("description")),
                status=str(status).strip(),
                resolution_date=str(fields.get("resolutiondate", "")).strip(),
            )
        )
        if len(tickets) >= limit:
            break
    return [ticket for ticket in tickets if ticket.key]


def load_issue_project_and_label(tools: list[Any], issue_key: str) -> tuple[str, str]:
    """
    Resolve current issue project key and primary label from Jira.

    Args:
        tools: Jira tools list.
        issue_key: Jira ticket key.
    Returns:
        Tuple: (project_key, primary_label).
    """
    issue_tool = _find_tool(tools, _GET_ISSUE_TOOL)
    if issue_tool is None or not issue_key:
        return "", ""
    try:
        result = issue_tool.run(issue_key=issue_key, fields=["project", "labels"])
    except Exception:
        logger.exception("Failed to fetch Jira issue for label history lookup: %s", issue_key)
        return "", ""
    payload = _safe_dict(result)
    issue = _safe_dict(payload.get("issue")) if "issue" in payload else payload
    fields = _safe_dict(issue.get("fields"))
    project = _safe_dict(fields.get("project"))
    labels = _safe_list(fields.get("labels"))
    return str(project.get("key", "")).strip(), extract_primary_label(labels)


def build_same_label_progress_context(
    tools: list[Any],
    project_key: str,
    label: str,
    exclude_issue_key: str,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> str:
    """
    Build structured same-label prior-progress context from Jira completed issues.

    Args:
        tools: Jira tools list.
        project_key: Current issue project key.
        label: Current issue label.
        exclude_issue_key: Current issue key.
        limit: Maximum number of historical tickets.
    Returns:
        Formatted context text for crew prompts and tasks.
    """
    if not project_key or not label:
        return "No comparable label history available."

    search_tool = _find_tool(tools, _SEARCH_ISSUES_TOOL)
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

    tickets = _parse_history_tickets(result=result, limit=limit)
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
