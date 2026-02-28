"""Workflow 4 PR body generation from code changes."""

import re
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


def _clean_summary(raw: str, ticket_key: str) -> str:
    """Clean commit-like title into readable PR summary."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    if re.match(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._/-]+$", text):
        text = text.split("/", 1)[1].replace("-", " ").replace("_", " ")
    if ticket_key:
        text = re.sub(rf"^{re.escape(ticket_key)}[\s:\-_/]+", "", text, flags=re.IGNORECASE)
    text = text.strip(" -_:,.;")
    if not text:
        return "Update implementation details for this ticket"

    # Keep full readable sentence; avoid forced truncation that creates "..."
    text = text.rstrip(".")
    return text[0].upper() + text[1:] if text else text


def _added_lines(patch: str) -> list[str]:
    lines: list[str] = []
    for line in (patch or "").splitlines():
        if line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
    return lines


def _collect_diff_signals(files: list[dict[str, Any]]) -> list[str]:
    route_re = re.compile(r'@\w+\.(get|post|put|patch|delete)\("([^"]+)"\)')
    fn_re = re.compile(r"\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
    bullets: list[str] = []
    seen: set[str] = set()

    for file in files:
        filename = str(file.get("filename") or "")
        patch = str(file.get("patch") or "")
        added = _added_lines(patch)
        if not added:
            continue

        routes: list[str] = []
        new_functions: list[str] = []
        new_tests: list[str] = []
        has_http_errors = False
        has_validation = False
        has_filtering = False
        has_pagination = False
        has_sorting = False

        for line in added:
            route_match = route_re.search(line)
            if route_match:
                method = route_match.group(1).upper()
                path = route_match.group(2)
                routes.append(f"{method} {path}")

            fn_match = fn_re.search(line)
            if fn_match:
                name = fn_match.group(1)
                if name.startswith("test_"):
                    new_tests.append(name)
                else:
                    new_functions.append(name)

            lowered = line.lower()
            if "httpexception(" in lowered or "status_code=" in lowered:
                has_http_errors = True
            if "field(" in lowered or "emailstr" in lowered or "valueerror" in lowered:
                has_validation = True
            if any(token in lowered for token in ("q:", "active_only", "role:", "filter")):
                has_filtering = True
            if any(token in lowered for token in ("limit", "offset")):
                has_pagination = True
            if any(token in lowered for token in ("sort_by", "order")):
                has_sorting = True

        if routes:
            item = f"- `{filename}`: added/updated routes {', '.join(routes[:4])}."
            if item not in seen:
                seen.add(item)
                bullets.append(item)

        if new_functions:
            preview = ", ".join(f"`{name}`" for name in new_functions[:4])
            item = f"- `{filename}`: added/updated functions {preview}."
            if item not in seen:
                seen.add(item)
                bullets.append(item)

        if new_tests:
            preview = ", ".join(f"`{name}`" for name in new_tests[:5])
            item = f"- `{filename}`: expanded tests with {preview}."
            if item not in seen:
                seen.add(item)
                bullets.append(item)

        if has_filtering or has_pagination or has_sorting:
            detail_parts: list[str] = []
            if has_filtering:
                detail_parts.append("filtering")
            if has_sorting:
                detail_parts.append("sorting")
            if has_pagination:
                detail_parts.append("pagination")
            item = f"- `{filename}`: introduced query controls for {', '.join(detail_parts)}."
            if item not in seen:
                seen.add(item)
                bullets.append(item)

        if has_validation or has_http_errors:
            detail_parts = []
            if has_validation:
                detail_parts.append("input/conflict validation")
            if has_http_errors:
                detail_parts.append("explicit HTTP error handling")
            item = f"- `{filename}`: added {', '.join(detail_parts)}."
            if item not in seen:
                seen.add(item)
                bullets.append(item)

    return bullets


def render_full_pr_details(
    *,
    ticket_key: str,
    pr_title: str,
    files: list[dict[str, Any]],
    summary_override: str | None = None,
    implementation_override: list[str] | None = None,
    validation_override: list[str] | None = None,
) -> str:
    """Render complete PR details block so developers do not need to write it manually."""
    grouped = _group_files(files)
    touched_areas = [name for name, items in grouped.items() if items]
    areas_line = ", ".join(touched_areas) if touched_areas else "Backend"
    summary = _clean_summary(summary_override or pr_title or ticket_key or "PR update", ticket_key)
    implementation_lines = implementation_override or _collect_diff_signals(files)
    if not implementation_lines:
        implementation_lines = [
            f"- Main code areas changed: {areas_line}.",
            "- Updated code paths were detected but detailed patch parsing was unavailable.",
        ]

    testing_hints = validation_override or []
    if not testing_hints:
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
        f"- Primary code area: {areas_line}\n\n"
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
