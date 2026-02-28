"""Parsing helpers for Jira same-label history responses."""

from dataclasses import dataclass
from typing import Any

from src.common.text_extract import extract_text


@dataclass
class HistoryTicket:
    """Compact shape for prior completed Jira ticket context."""

    key: str
    summary: str
    description_excerpt: str
    status: str
    resolution_date: str
    implementation_details: str = ""


def safe_dict(value: Any) -> dict[str, Any]:
    """Return dict-like values, else empty dict."""
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    """Return list-like values, else empty list."""
    return value if isinstance(value, list) else []


def extract_primary_component(components: list[Any]) -> str:
    """Return first non-empty component name."""
    for component in components:
        name = str(safe_dict(component).get("name", "")).strip()
        if name:
            return name
    return ""


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace into a single space."""
    return " ".join(text.split())


def description_excerpt(value: Any, max_chars: int = 220) -> str:
    """Build one-line short excerpt from Jira description payload."""
    plain = normalize_whitespace(extract_text(value))
    if not plain:
        return "No implementation notes provided."
    if len(plain) <= max_chars:
        return plain
    return plain[: max_chars - 3].rstrip() + "..."


WF6_COMMENT_MARKER = "<!-- leadsync:wf6 -->"


def extract_wf6_implementation(response_text: str, max_chars: int = 300) -> str:
    """Extract WF6 implementation summary from a JIRA_GET_ISSUE response string.

    Args:
        response_text: Stringified JIRA_GET_ISSUE response.
        max_chars: Maximum length of returned text.
    Returns:
        Implementation details string, or empty string if not found.
    """
    marker_pos = response_text.find(WF6_COMMENT_MARKER)
    if marker_pos < 0:
        return ""
    after_marker = response_text[marker_pos + len(WF6_COMMENT_MARKER):]
    lines = after_marker.splitlines()
    summary_line = ""
    files_line = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("IMPLEMENTATION_SUMMARY:"):
            summary_line = stripped[len("IMPLEMENTATION_SUMMARY:"):].strip()
        elif stripped.startswith("FILES_CHANGED:"):
            files_line = stripped[len("FILES_CHANGED:"):].strip()
    if not summary_line:
        raw_lines = [
            l.strip()
            for l in lines
            if l.strip() and not l.strip().startswith("Implementation scan for")
        ]
        summary_line = " ".join(raw_lines[:3])
    result = summary_line
    if files_line and files_line.lower() != "none":
        result += f" Files: {files_line}"
    if len(result) > max_chars:
        result = result[:max_chars - 3].rstrip() + "..."
    return result


def extract_issue_list(result: Any) -> list[dict[str, Any]]:
    """Extract issue list from common Composio response envelope shapes."""
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    payload = safe_dict(result)
    for key in ("issues", "data", "result", "response"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        nested = safe_dict(candidate).get("issues")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return []


def parse_history_tickets(result: Any, limit: int) -> list[HistoryTicket]:
    """Parse compact history ticket rows from search result payload."""
    rows: list[HistoryTicket] = []
    for issue in extract_issue_list(result):
        fields = safe_dict(issue.get("fields"))
        status = safe_dict(fields.get("status")).get("name", "Done")
        rows.append(
            HistoryTicket(
                key=str(issue.get("key", "")),
                summary=str(fields.get("summary", "")).strip(),
                description_excerpt=description_excerpt(fields.get("description")),
                status=str(status).strip(),
                resolution_date=str(fields.get("resolutiondate", "")).strip(),
            )
        )
        if len(rows) >= limit:
            break
    return [row for row in rows if row.key]
