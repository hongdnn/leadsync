"""Workflow 2 digest parsing helpers."""

import re

AREA_LINE_RE = re.compile(
    r"AREA:\s*(?P<area>.+?)\s*\|\s*SUMMARY:\s*(?P<summary>.+?)\s*\|\s*(?:DECISIONS|RISKS):\s*(?P<risks>.+)",
    flags=re.IGNORECASE,
)


def parse_digest_areas(digest_text: str) -> list[tuple[str, str, str]]:
    """
    Parse normalized digest area lines.

    Args:
        digest_text: Writer task output text.
    Returns:
        List of (area, summary, risks) tuples.
    """
    rows: list[tuple[str, str, str]] = []
    for raw_line in digest_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = AREA_LINE_RE.match(line)
        if match:
            rows.append(
                (
                    match.group("area").strip(),
                    match.group("summary").strip(),
                    match.group("risks").strip(),
                )
            )
    if rows:
        return rows
    fallback = digest_text.strip()
    if not fallback:
        return []
    return [("general", fallback[:240], "No explicit risks captured.")]
