"""Workflow 1 prompt artifact normalization and persistence helpers."""

from pathlib import Path
import re
import tempfile
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
    team_preferences: str,
) -> str:
    """Build required-section markdown from reasoner output with safe fallback."""
    if reasoner_text and has_required_sections(reasoner_text):
        return _replace_key_files_section(reasoner_text.strip(), key_files_markdown) + "\n"
    summary_text = summary.strip() or "No summary provided."
    context_text = gathered_context.strip() or "No additional context gathered."
    constraints_text = (
        "- Stay aligned with Jira scope and linked context.\n"
        "- Keep output paste-ready for the assignee.\n"
        "- Follow repository standards and existing patterns."
    )
    rules_text = team_preferences.strip() or "- No team preferences found; use backend defaults."
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


def _replace_key_files_section(markdown: str, key_files_markdown: str) -> str:
    """Replace existing `## Key Files` section body with normalized key-file markdown."""
    marker = "## Key Files"
    if marker not in markdown:
        return markdown
    lines = markdown.splitlines()
    out: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if line.strip() == marker and not replaced:
            out.append(line)
            if key_files_markdown.strip():
                out.extend(key_files_markdown.splitlines())
            i += 1
            while i < len(lines):
                candidate = lines[i]
                if candidate.startswith("## ") and candidate.strip() != marker:
                    break
                i += 1
            replaced = True
            continue
        out.append(line)
        i += 1
    return "\n".join(out).strip()


def safe_issue_key_for_filename(issue_key: str) -> str:
    """Sanitize issue key for local filesystem usage."""
    return re.sub(r"[^A-Za-z0-9_.-]", "-", issue_key or "UNKNOWN")


def upload_prompt_to_jira(tools: list[Any], issue_key: str, markdown: str) -> Path:
    """Write prompt markdown to a temp file, upload to Jira, and return the temp path.

    Args:
        tools: Composio tool list containing JIRA_ADD_ATTACHMENT.
        issue_key: Jira issue key for the attachment.
        markdown: Prompt markdown content to upload.
    Returns:
        Path to the temporary file (caller may clean up).
    Raises:
        RuntimeError: When JIRA_ADD_ATTACHMENT tool is unavailable or fails.
    """
    tool = find_tool_by_name(tools, "JIRA_ADD_ATTACHMENT")
    if tool is None:
        raise RuntimeError("JIRA_ADD_ATTACHMENT tool is required for Workflow 1.")
    filename = f"prompt-{safe_issue_key_for_filename(issue_key)}.md"
    tmp_dir = tempfile.mkdtemp(prefix="leadsync_")
    tmp_path = Path(tmp_dir) / filename
    tmp_path.write_text(markdown, encoding="utf-8")
    resolved = tmp_path.resolve()
    try:
        response = tool.run(
            issue_key=issue_key,
            local_file_path=str(resolved),
            file_to_upload=str(resolved),
        )
        if response_indicates_failure(response):
            details = summarize_tool_response(response)
            raise RuntimeError(f"JIRA_ADD_ATTACHMENT failed: {details}")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
            Path(tmp_dir).rmdir()
        except OSError:
            pass
    return resolved
