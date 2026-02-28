"""Deterministic Jira write-back helpers for Workflow 1."""

import logging
import re
from typing import Any

from src.common.tool_helpers import find_tool_by_name
from src.common.tool_response import response_indicates_failure, summarize_tool_response

MAX_HISTORY_LINES = 4
MAX_KEY_FILE_LINES = 4
MAX_SECTION_LINES = 4


def _clean_lines(text: str, limit: int) -> list[str]:
    """Normalize multiline text into compact plain-text lines."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ")):
            line = line[2:].strip()
        line = line.strip("`")
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _extract_section(markdown: str, heading: str) -> str:
    """Extract section body from markdown by heading."""
    pattern = re.compile(rf"{re.escape(heading)}\n(?P<body>.*?)(?=\n## |\Z)", re.DOTALL)
    match = pattern.search(markdown)
    return match.group("body").strip() if match else ""


def build_comment_text(
    *,
    issue_key: str,
    summary: str,
    same_label_history: str,
    key_files_markdown: str,
    repo_owner: str,
    repo_name: str,
) -> str:
    """Build plain-text Jira comment content with progress and implementation path."""
    history_lines = _clean_lines(same_label_history, MAX_HISTORY_LINES)
    key_file_lines = _clean_lines(key_files_markdown, MAX_KEY_FILE_LINES)
    lines = ["Previous same-label progress:"]
    lines.extend(history_lines or ["No completed same-label tickets found."])
    lines.append("Recommended implementation path for current task:")
    lines.append(f"Target repository: {repo_owner}/{repo_name}.")
    lines.append(f"Issue scope: {issue_key} - {(summary or 'No summary provided.').strip()}")
    lines.extend(key_file_lines or ["No key files were identified."])
    lines.append("Validate behavior with focused tests before marking done.")
    return "\n".join(lines)


def build_description_text(
    *,
    issue_key: str,
    summary: str,
    prompt_markdown: str,
    key_files_markdown: str,
    repo_owner: str,
    repo_name: str,
) -> str:
    """Build plain-text Jira description update from prompt sections."""
    constraints = _clean_lines(_extract_section(prompt_markdown, "## Constraints"), MAX_SECTION_LINES)
    outputs = _clean_lines(_extract_section(prompt_markdown, "## Expected Output"), MAX_SECTION_LINES)
    key_files = _clean_lines(key_files_markdown, MAX_KEY_FILE_LINES)
    lines = [
        f"Technical implementation guidance for {issue_key}: {(summary or 'No summary provided.').strip()}",
        f"Repository target: {repo_owner}/{repo_name}.",
        "Key files to inspect first:",
    ]
    lines.extend(key_files or ["No key files were identified."])
    lines.append("Constraints:")
    lines.extend(constraints or ["Respect existing Jira scope and repository patterns."])
    lines.append("Expected output:")
    lines.extend(outputs or ["Code changes, tests, and docs updates where needed."])
    lines.append("See the attached prompt file for full implementation rules and team preferences.")
    return "\n".join(lines)


def _run_required_tool(tool: Any, action: str, **kwargs: Any) -> Any:
    """Run a tool and raise RuntimeError when response indicates failure."""
    response = tool.run(**kwargs)
    if response_indicates_failure(response):
        details = summarize_tool_response(response)
        raise RuntimeError(f"{action} failed: {details}")
    return response


def apply_jira_writeback(
    *,
    tools: list[Any],
    issue_key: str,
    comment_text: str,
    description_text: str,
    logger: logging.Logger,
) -> None:
    """Write deterministic description and comment updates via Jira tools."""
    edit_tool = find_tool_by_name(tools, "JIRA_EDIT_ISSUE")
    comment_tool = find_tool_by_name(tools, "JIRA_ADD_COMMENT")
    if edit_tool is None:
        logger.warning("Workflow 1: JIRA_EDIT_ISSUE tool unavailable; skipping description update.")
    else:
        _run_required_tool(
            edit_tool,
            "JIRA_EDIT_ISSUE",
            issue_id_or_key=issue_key,
            description=description_text,
        )
    if comment_tool is None:
        logger.warning("Workflow 1: JIRA_ADD_COMMENT tool unavailable; skipping comment write-back.")
    else:
        _run_required_tool(
            comment_tool,
            "JIRA_ADD_COMMENT",
            issue_id_or_key=issue_key,
            comment=comment_text,
        )

