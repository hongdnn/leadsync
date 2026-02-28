"""Workflow 1 key-file parsing and formatting helpers."""

from dataclasses import dataclass
import re

MAX_KEY_FILES = 8
_VALID_CONFIDENCE = {"high", "medium", "low"}
_KEY_FILE_PATTERN = re.compile(
    r"^KEY_FILE:\s*(?P<path>[^|]+?)\s*\|\s*WHY:\s*(?P<why>[^|]+?)\s*\|\s*CONFIDENCE:\s*(?P<confidence>\w+)\s*$",
    re.IGNORECASE,
)


@dataclass
class KeyFile:
    """Normalized key-file record extracted from gatherer output."""

    path: str
    why: str
    confidence: str


def parse_key_files(text: str, limit: int = MAX_KEY_FILES) -> list[KeyFile]:
    """Extract up to `limit` key-file records from gatherer output text."""
    seen_paths: set[str] = set()
    parsed: list[KeyFile] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith(("- ", "* ")):
            line = line[2:].strip()
        match = _KEY_FILE_PATTERN.match(line)
        if not match:
            continue
        path = match.group("path").strip().strip("`")
        why = match.group("why").strip()
        confidence = match.group("confidence").strip().lower()
        if not path or not why:
            continue
        if confidence not in _VALID_CONFIDENCE:
            confidence = "medium"
        dedupe_key = path.lower()
        if dedupe_key in seen_paths:
            continue
        seen_paths.add(dedupe_key)
        parsed.append(KeyFile(path=path, why=why, confidence=confidence))
        if len(parsed) >= limit:
            break
    return parsed


def format_key_files_markdown(key_files: list[KeyFile]) -> str:
    """Render key-file records as deterministic markdown bullet lines."""
    return "\n".join(
        f"- `{item.path}` - {item.why} (confidence: {item.confidence})" for item in key_files
    )
