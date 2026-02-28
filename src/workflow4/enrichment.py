"""Workflow 4 PR body generation from code changes."""

from typing import Any

ENRICHMENT_MARKER_START = "<!-- leadsync:pr-details:start -->"
ENRICHMENT_MARKER_END = "<!-- leadsync:pr-details:end -->"


def _category_for_path(path: str) -> str:
    lowered = path.lower()
    if any(token in lowered for token in ("test", "spec", "__tests__")):
        return "Testing"
    if any(token in lowered for token in ("ui/", "frontend", "web/", "components/", "pages/")):
        return "Frontend"
    if any(token in lowered for token in ("db/", "database", "migration", "schema", "sql")):
        return "Database"
    if any(token in lowered for token in ("docs/", "readme", ".md")):
        return "Documentation"
    return "Backend"


def _group_files(files: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "Backend": [],
        "Frontend": [],
        "Database": [],
        "Testing": [],
        "Documentation": [],
    }
    for file in files:
        path = str(file.get("filename") or "")
        grouped[_category_for_path(path)].append(file)
    return grouped


def _render_file_lines(files: list[dict[str, Any]], max_files: int = 15) -> str:
    if not files:
        return "- No changed files detected from webhook tooling."
    lines: list[str] = []
    for file in files[:max_files]:
        filename = str(file.get("filename") or "unknown")
        status = str(file.get("status") or "modified")
        additions = int(file.get("additions") or 0)
        deletions = int(file.get("deletions") or 0)
        lines.append(f"- `{filename}` ({status}, +{additions}/-{deletions})")
    remaining = len(files) - min(len(files), max_files)
    if remaining > 0:
        lines.append(f"- ... and {remaining} more files")
    return "\n".join(lines)


def render_full_pr_details(
    *,
    ticket_key: str,
    pr_title: str,
    files: list[dict[str, Any]],
) -> str:
    """Render complete PR details block so developers do not need to write it manually."""
    grouped = _group_files(files)
    touched_areas = [name for name, items in grouped.items() if items]
    areas_line = ", ".join(touched_areas) if touched_areas else "Backend"
    summary = pr_title or ticket_key or "PR update"

    implementation_lines = [
        f"- This PR focuses on: {summary}.",
        f"- Main code areas changed: {areas_line}.",
        "- Changes were inferred directly from the modified files list.",
    ]

    testing_hints: list[str] = []
    if grouped["Testing"]:
        testing_hints.append("- Includes test file changes; run unit/integration suite for touched modules.")
    else:
        testing_hints.append("- No test files detected in this PR; validate if tests should be added.")
    if grouped["Database"]:
        testing_hints.append("- Database-related changes detected; verify migrations and backward compatibility.")
    if grouped["Frontend"]:
        testing_hints.append("- Frontend changes detected; verify UI behavior manually in staging.")

    return (
        f"{ENRICHMENT_MARKER_START}\n"
        "## Summary\n"
        f"{summary}\n\n"
        "## Context\n"
        f"- Ticket key: {ticket_key or 'not detected from branch/title/body'}\n"
        "- Auto-generated from code changes.\n\n"
        "## Implementation Details\n"
        f"{chr(10).join(implementation_lines)}\n\n"
        "## Files Changed\n"
        f"{_render_file_lines(files)}\n\n"
        "## Suggested Validation\n"
        f"{chr(10).join(testing_hints)}\n"
        f"{ENRICHMENT_MARKER_END}"
    )


def upsert_enrichment_block(existing_body: str, block: str) -> str:
    """Replace existing managed block or append a new one."""
    body = (existing_body or "").strip()
    if ENRICHMENT_MARKER_START in body and ENRICHMENT_MARKER_END in body:
        start = body.index(ENRICHMENT_MARKER_START)
        end = body.index(ENRICHMENT_MARKER_END) + len(ENRICHMENT_MARKER_END)
        updated = f"{body[:start].rstrip()}\n\n{block}\n\n{body[end:].lstrip()}".strip()
        return updated
    if not body:
        return block
    return f"{body}\n\n{block}"
