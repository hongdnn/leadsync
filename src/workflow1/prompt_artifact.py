"""Workflow 1 prompt artifact normalization and persistence helpers."""

from pathlib import Path
import re
from typing import Any

from src.common.tool_helpers import find_tool_by_name
from src.common.tool_response import response_indicates_failure, summarize_tool_response

REQUIRED_SECTIONS = [
    "## Task",
    "## Context",
    "## Key Files",
    "## Constraints",
    "## Implementation Rules",
    "## Expected Output",
]


def has_required_sections(markdown: str) -> bool:
    """Return whether markdown contains all required Workflow 1 sections."""
    return all(section in markdown for section in REQUIRED_SECTIONS)


def normalize_prompt_markdown(
    reasoner_text: str,
    issue_key: str,
    summary: str,
    gathered_context: str,
    key_files_markdown: str,
    ruleset_content: str,
) -> str:
    """Build required-section markdown from reasoner output with safe fallback."""
    if reasoner_text and has_required_sections(reasoner_text):
        return reasoner_text.strip() + "\n"
    summary_text = summary.strip() or "No summary provided."
    context_text = gathered_context.strip() or "No additional context gathered."
    constraints_text = (
        "- Stay aligned with Jira scope and linked context.\n"
        "- Keep output paste-ready for the assignee.\n"
        "- Follow repository standards and existing patterns."
    )
    rules_text = ruleset_content.strip() or "- No ruleset content found; use backend defaults."
    expected_output = reasoner_text.strip() or "Provide an implementation-ready prompt."
    return (
        "## Task\n"
        f"- Ticket: {issue_key}\n"
        f"- Summary: {summary_text}\n\n"
        "## Context\n"
        f"{context_text}\n\n"
        "## Key Files\n"
        f"{key_files_markdown}\n\n"
        "## Constraints\n"
        f"{constraints_text}\n\n"
        "## Implementation Rules\n"
        f"{rules_text}\n\n"
        "## Expected Output\n"
        f"{expected_output}\n"
    )


def safe_issue_key_for_filename(issue_key: str) -> str:
    """Sanitize issue key for local filesystem usage."""
    return re.sub(r"[^A-Za-z0-9_.-]", "-", issue_key or "UNKNOWN")


def write_prompt_file(artifact_dir: Path, issue_key: str, markdown: str) -> Path:
    """Write workflow1 prompt artifact and return absolute file path."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = artifact_dir / f"prompt-{safe_issue_key_for_filename(issue_key)}.md"
    prompt_path.write_text(markdown, encoding="utf-8")
    return prompt_path.resolve()


def attach_prompt_file(tools: list[Any], issue_key: str, file_path: Path) -> Any:
    """Attach local prompt file to Jira issue through Composio tool."""
    tool = find_tool_by_name(tools, "JIRA_ADD_ATTACHMENT")
    if tool is None:
        raise RuntimeError("JIRA_ADD_ATTACHMENT tool is required for Workflow 1.")
    resolved = file_path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Prompt file not found for attachment: {resolved}")
    response = tool.run(
        issue_key=issue_key,
        local_file_path=str(resolved),
        file_to_upload=str(resolved),
    )
    if response_indicates_failure(response):
        details = summarize_tool_response(response)
        raise RuntimeError(f"JIRA_ADD_ATTACHMENT failed: {details}")
    return response
