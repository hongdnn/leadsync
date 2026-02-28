"""Workflow 1 payload parsing helpers."""

from dataclasses import dataclass
from typing import Any

from src.common.text_extract import extract_text
from src.common.jira_history_core import extract_primary_label


def safe_dict(value: Any) -> dict[str, Any]:
    """Return dict value or empty dict."""
    return value if isinstance(value, dict) else {}


@dataclass
class IssueContext:
    """Normalized Jira payload context used by Workflow 1."""

    issue_key: str
    summary: str
    issue_description: str
    labels: list[str]
    assignee: str
    project_key: str
    component_names: list[str]
    primary_label: str
    primary_component: str


def parse_issue_context(payload: dict[str, Any]) -> IssueContext:
    """Normalize Jira webhook payload into a stable context object."""
    issue = safe_dict(payload.get("issue")) or safe_dict(payload.get("workItem"))
    # Fallback: if no wrapper found but payload itself looks like an issue, use it directly.
    if not issue and ("key" in payload or "id" in payload):
        issue = payload
    fields = safe_dict(issue.get("fields"))
    issue_key = issue.get("key", issue.get("id", "UNKNOWN"))
    labels_raw = fields.get("labels", issue.get("labels", []))
    labels = [label for label in labels_raw if isinstance(label, str)] if isinstance(labels_raw, list) else []
    components_raw = fields.get("components", issue.get("components", []))
    component_names = []
    if isinstance(components_raw, list):
        component_names = [item.get("name", "") for item in components_raw if isinstance(item, dict)]
    assignee_data = safe_dict(fields.get("assignee")) or safe_dict(issue.get("assignee"))
    assignee = (
        assignee_data.get("displayName")
        or assignee_data.get("display_name")
        or assignee_data.get("name")
        or "Unassigned"
    )
    project = safe_dict(fields.get("project")) or safe_dict(issue.get("project"))
    primary_component = next((name for name in component_names if isinstance(name, str) and name), "")
    return IssueContext(
        issue_key=str(issue_key),
        summary=str(fields.get("summary", issue.get("summary", ""))),
        issue_description=extract_text(fields.get("description", issue.get("description", ""))),
        labels=labels,
        assignee=str(assignee),
        project_key=str(project.get("key", "")),
        component_names=component_names,
        primary_label=extract_primary_label(labels),
        primary_component=primary_component,
    )
