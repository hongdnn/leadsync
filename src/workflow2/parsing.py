"""Workflow 2 digest parsing helpers."""

import re
from dataclasses import dataclass, field

# Legacy single-line format: AREA: x | SUMMARY: y | DECISIONS: z
AREA_LINE_RE = re.compile(
    r"AREA:\s*(?P<area>.+?)\s*\|\s*SUMMARY:\s*(?P<summary>.+?)\s*\|\s*(?:DECISIONS|RISKS):\s*(?P<risks>.+)",
    flags=re.IGNORECASE,
)

# Multi-line block field patterns (single-line fields parsed individually)
_FIELD_RE = {
    "area": re.compile(r"^AREA:\s*(.+)", re.IGNORECASE),
    "authors": re.compile(r"^AUTHORS:\s*(.+)", re.IGNORECASE),
    "commits": re.compile(r"^COMMITS:\s*(.+)", re.IGNORECASE),
    "files": re.compile(r"^FILES:\s*(.+)", re.IGNORECASE),
    "summary": re.compile(r"^SUMMARY:\s*(.+)", re.IGNORECASE),
    "decisions": re.compile(r"^(?:DECISIONS|RISKS):\s*(.+)", re.IGNORECASE),
}

# CHANGES is a multi-line field: starts with "CHANGES:" header, followed by
# bullet lines (- ...) that should all be captured as a single string.
_CHANGES_HEADER_RE = re.compile(r"^CHANGES:\s*(.*)", re.IGNORECASE)


@dataclass
class DigestArea:
    """Parsed digest area block with enriched fields."""

    area: str = ""
    authors: str = ""
    commits: str = "0"
    files: str = ""
    changes: str = ""
    summary: str = ""
    decisions: str = ""


def parse_digest_areas(digest_text: str) -> list[tuple[str, str, str]]:
    """
    Parse digest area blocks from writer output.

    Supports both the new multi-line block format (--- delimited)
    and the legacy single-line pipe format for backward compatibility.

    Args:
        digest_text: Writer task output text.
    Returns:
        List of (area, summary, risks) tuples.
    """
    blocks = _parse_blocks(digest_text)
    if blocks:
        return [
            (b.area.strip(), b.summary.strip(), b.decisions.strip())
            for b in blocks
            if b.area.strip()
        ]

    # Fallback: legacy single-line format
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


def parse_digest_blocks(digest_text: str) -> list[DigestArea]:
    """
    Parse digest into rich DigestArea blocks with all fields.

    Args:
        digest_text: Writer task output text.
    Returns:
        List of DigestArea dataclasses with area, authors, commits, files,
        summary, and decisions fields populated.
    """
    blocks = _parse_blocks(digest_text)
    if blocks:
        return blocks

    # Fallback: build DigestArea from legacy single-line format
    rows = parse_digest_areas(digest_text)
    return [
        DigestArea(area=area, summary=summary, decisions=decisions)
        for area, summary, decisions in rows
    ]


def _parse_blocks(digest_text: str) -> list[DigestArea]:
    """
    Parse --- delimited multi-line blocks into DigestArea instances.

    Only activates when the text contains at least one '---' delimiter.
    This prevents false matches on legacy single-line pipe format.

    Handles the multi-line CHANGES field: once a "CHANGES:" header is seen,
    subsequent bullet lines ("- ...") are collected until the next field
    header, delimiter, or end of block.

    Args:
        digest_text: Raw writer output text.
    Returns:
        List of DigestArea instances, empty if no blocks found.
    """
    if "---" not in digest_text:
        return []

    blocks: list[DigestArea] = []
    current: DigestArea | None = None
    in_block = False
    in_changes = False
    changes_lines: list[str] = []

    for raw_line in digest_text.splitlines():
        line = raw_line.strip()
        if line == "---":
            # Flush pending CHANGES before closing block
            if current and changes_lines:
                current.changes = "\n".join(changes_lines)
                changes_lines = []
                in_changes = False
            if current and current.area:
                blocks.append(current)
            current = DigestArea()
            in_block = True
            in_changes = False
            continue

        if not in_block or current is None:
            continue

        # Check for CHANGES: header
        cm = _CHANGES_HEADER_RE.match(line)
        if cm:
            in_changes = True
            changes_lines = []
            # Inline content after "CHANGES:" (rare but possible)
            inline = cm.group(1).strip()
            if inline:
                changes_lines.append(inline)
            continue

        # Collect bullet lines while inside CHANGES
        if in_changes:
            if line.startswith("- "):
                changes_lines.append(line)
                continue
            else:
                # Non-bullet line ends the CHANGES section
                current.changes = "\n".join(changes_lines)
                changes_lines = []
                in_changes = False
                # Fall through to parse this line as a normal field

        for field_name, pattern in _FIELD_RE.items():
            m = pattern.match(line)
            if m:
                setattr(current, field_name, m.group(1).strip())
                break

    # Capture last block if text doesn't end with ---
    if current and changes_lines:
        current.changes = "\n".join(changes_lines)
    if current and current.area:
        blocks.append(current)

    return blocks
