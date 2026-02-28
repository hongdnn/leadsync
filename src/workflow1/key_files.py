"""Workflow 1 key-file parsing/formatting plus local key-file suggestion helpers."""

from dataclasses import dataclass
from pathlib import Path
import re

MAX_KEY_FILES = 8
_VALID_CONFIDENCE = {"high", "medium", "low"}
_DEMO_PREFIX = "demo/"
_SUGGESTABLE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".kt",
    ".sql",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
}
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


def is_demo_path(path: str) -> bool:
    """Return whether path points under repo-local demo directory."""
    normalized = path.replace("\\", "/").strip().lstrip("./")
    return normalized.startswith(_DEMO_PREFIX)


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


def filter_demo_key_files(key_files: list[KeyFile], limit: int = MAX_KEY_FILES) -> list[KeyFile]:
    """Keep only demo-scoped key files (deduped, order-preserving)."""
    filtered: list[KeyFile] = []
    seen_paths: set[str] = set()
    for item in key_files:
        if not is_demo_path(item.path):
            continue
        dedupe_key = item.path.lower()
        if dedupe_key in seen_paths:
            continue
        seen_paths.add(dedupe_key)
        filtered.append(item)
        if len(filtered) >= limit:
            break
    return filtered


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 3}


def _iter_demo_files(repo_root: Path) -> list[Path]:
    demo_root = repo_root / "demo"
    if not demo_root.exists():
        return []
    files: list[Path] = []
    for path in demo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _SUGGESTABLE_SUFFIXES:
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        files.append(path)
    return files


def suggest_demo_key_files(
    *,
    issue_text: str,
    repo_root: Path,
    limit: int = MAX_KEY_FILES,
) -> list[KeyFile]:
    """Suggest demo file candidates by matching ticket text tokens to file path tokens."""
    issue_tokens = _tokenize(issue_text)
    if not issue_tokens:
        issue_tokens = {"api", "service", "test"}
    candidates: list[tuple[int, str]] = []
    for file_path in _iter_demo_files(repo_root):
        rel = file_path.relative_to(repo_root).as_posix()
        path_tokens = _tokenize(rel.replace("/", " "))
        overlap = issue_tokens.intersection(path_tokens)
        score = len(overlap)
        if rel.endswith("test_users.py"):
            score += 1
        if rel.endswith("users.py") or rel.endswith("user_service.py"):
            score += 1
        if score <= 0:
            continue
        candidates.append((score, rel))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = candidates[:limit]
    if not selected:
        return []
    suggested: list[KeyFile] = []
    for score, rel in selected:
        confidence = "high" if score >= 4 else "medium"
        why = "Suggested from ticket description keyword overlap within demo project scope."
        suggested.append(KeyFile(path=rel, why=why, confidence=confidence))
    return suggested


def format_key_files_markdown(key_files: list[KeyFile]) -> str:
    """Render key-file records as deterministic markdown bullet lines."""
    return "\n".join(
        f"- `{item.path}` - {item.why} (confidence: {item.confidence})" for item in key_files
    )
