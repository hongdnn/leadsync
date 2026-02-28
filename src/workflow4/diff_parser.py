"""Workflow 4 file normalization and unified diff parsing."""

from collections import defaultdict
import os
from typing import Any
import urllib.request


def _normalize_files(items: list[Any]) -> list[dict[str, Any]]:
    """Normalize raw file entries into consistent dict format."""
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or item.get("path") or "").strip()
        if not filename:
            continue
        normalized.append(
            {
                "filename": filename,
                "status": str(item.get("status") or "modified"),
                "additions": int(item.get("additions") or 0),
                "deletions": int(item.get("deletions") or 0),
                "patch": str(item.get("patch") or ""),
            }
        )
    return normalized


def _extract_file_items(plain: Any) -> list[Any]:
    """Extract file list from various response shapes."""
    if isinstance(plain, list):
        return plain
    if isinstance(plain, dict):
        for key in ("files", "data", "items", "pull_request_files", "changed_files"):
            value = plain.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = value.get("files")
                if isinstance(nested, list):
                    return nested
    return []


def _merge_files_by_path(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate and merge file entries by path, preserving first-seen order."""
    merged: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"filename": "", "status": "modified", "additions": 0, "deletions": 0, "patch": ""}
    )
    order: list[str] = []

    for file in files:
        path = str(file.get("filename") or "").strip()
        if not path:
            continue
        if path not in merged:
            order.append(path)
        item = merged[path]
        item["filename"] = path
        item["status"] = str(file.get("status") or item["status"])
        item["additions"] = int(item.get("additions") or 0) + int(file.get("additions") or 0)
        item["deletions"] = int(item.get("deletions") or 0) + int(file.get("deletions") or 0)
        patch = str(file.get("patch") or "").strip()
        if patch:
            if item["patch"]:
                item["patch"] = f"{item['patch']}\n{patch}"
            else:
                item["patch"] = patch

    return [merged[path] for path in order]


def _status_from_diff_headers(headers: list[str]) -> str:
    """Detect file status (added/removed/renamed/modified) from diff headers."""
    joined = "\n".join(headers).lower()
    if "new file mode" in joined:
        return "added"
    if "deleted file mode" in joined:
        return "removed"
    if "rename from" in joined and "rename to" in joined:
        return "renamed"
    return "modified"


def _parse_unified_diff(diff_text: str) -> list[dict[str, Any]]:
    """Parse unified diff text into normalized file entries."""
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    headers: list[str] = []

    def flush() -> None:
        nonlocal current, headers
        if current is None:
            return
        current["status"] = _status_from_diff_headers(headers)
        files.append(current)
        current = None
        headers = []

    for raw_line in diff_text.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("diff --git "):
            flush()
            parts = line.split(" ")
            b_path = parts[-1] if len(parts) >= 4 else ""
            if b_path.startswith("b/"):
                b_path = b_path[2:]
            current = {
                "filename": b_path,
                "status": "modified",
                "additions": 0,
                "deletions": 0,
                "patch": "",
            }
            headers = [line]
            continue
        if current is None:
            continue

        if line.startswith(("index ", "--- ", "+++ ", "new file mode", "deleted file mode", "rename from", "rename to")):
            headers.append(line)
            if line.startswith("+++ b/"):
                current["filename"] = line[6:]
            continue

        if line.startswith("@@") or line.startswith("+") or line.startswith("-") or line.startswith(" "):
            current["patch"] = f"{current['patch']}\n{line}".strip()
            if line.startswith("+") and not line.startswith("+++"):
                current["additions"] += 1
            elif line.startswith("-") and not line.startswith("---"):
                current["deletions"] += 1
            continue

        headers.append(line)

    flush()
    return _merge_files_by_path(files)


def fetch_pr_diff_http(owner: str, repo: str, number: int) -> list[dict[str, Any]]:
    """Fallback: fetch PR unified diff directly from GitHub and parse file changes."""
    diff_url = f"https://github.com/{owner}/{repo}/pull/{number}.diff"
    request = urllib.request.Request(diff_url, headers={"Accept": "application/vnd.github.v3.diff"})
    token = os.getenv("LEADSYNC_GITHUB_TOKEN", "").strip() or os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - controlled URL format
        body = response.read().decode("utf-8", errors="replace")
    return _parse_unified_diff(body)
