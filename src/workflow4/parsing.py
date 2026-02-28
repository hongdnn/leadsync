"""Workflow 4 parsing helpers."""

from dataclasses import dataclass
import re
from typing import Any

JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


@dataclass
class PRContext:
    """Normalized pull request context extracted from webhook payload."""

    action: str
    owner: str
    repo: str
    number: int
    html_url: str
    title: str
    body: str
    branch: str
    base_sha: str
    head_sha: str
    jira_key: str


def _safe_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def extract_jira_key(*candidates: str) -> str:
    """Extract first Jira key occurrence from any candidate strings."""
    for text in candidates:
        match = JIRA_KEY_RE.search(text or "")
        if match:
            return match.group(1)
    return ""


def parse_pr_context(payload: dict[str, Any]) -> PRContext:
    """Parse minimal PR context from GitHub webhook payload."""
    pr = payload.get("pull_request", {}) if isinstance(payload.get("pull_request"), dict) else {}
    repository = payload.get("repository", {}) if isinstance(payload.get("repository"), dict) else {}
    owner_obj = repository.get("owner", {}) if isinstance(repository.get("owner"), dict) else {}
    head = pr.get("head", {}) if isinstance(pr.get("head"), dict) else {}
    base = pr.get("base", {}) if isinstance(pr.get("base"), dict) else {}

    title = _safe_str(pr.get("title"))
    body = _safe_str(pr.get("body"))
    branch = _safe_str(head.get("ref"))
    jira_key = extract_jira_key(branch, title, body)

    return PRContext(
        action=_safe_str(payload.get("action")).lower(),
        owner=_safe_str(owner_obj.get("login")),
        repo=_safe_str(repository.get("name")),
        number=int(pr.get("number") or 0),
        html_url=_safe_str(pr.get("html_url")),
        title=title,
        body=body,
        branch=branch,
        base_sha=_safe_str(base.get("sha")),
        head_sha=_safe_str(head.get("sha")),
        jira_key=jira_key,
    )
