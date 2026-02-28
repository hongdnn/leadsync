"""Workflow 4 tool operations for PR auto-description."""

from collections import defaultdict
import os
from typing import Any
import urllib.request


def to_plain(value: Any) -> Any:
    """Best-effort normalize SDK objects into plain dict/list primitives."""
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_plain(v) for v in value]
    if hasattr(value, "model_dump"):
        return to_plain(value.model_dump())
    if hasattr(value, "dict"):
        return to_plain(value.dict())
    if hasattr(value, "__dict__"):
        return to_plain(vars(value))
    return value


def _tool_name(tool: Any) -> str:
    return str(getattr(tool, "name", "")).upper()


def find_tool(tools: list[Any], *names: str) -> Any | None:
    """Find first tool whose name matches one of the provided names."""
    want = {name.upper() for name in names}
    for tool in tools:
        if _tool_name(tool) in want:
            return tool
    return None


def run_tool_variants(tool: Any, variants: list[dict[str, Any]]) -> Any:
    """Run a tool with argument variants and return first successful response."""
    last_err: Exception | None = None
    for args in variants:
        try:
            return tool.run(**args)
        except Exception as exc:  # pragma: no cover - external SDK variability
            last_err = exc
    if last_err:
        raise last_err
    raise RuntimeError("No argument variants supplied for tool call.")


def _normalize_files(items: list[Any]) -> list[dict[str, Any]]:
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


def _fetch_pr_diff_http(owner: str, repo: str, number: int) -> list[dict[str, Any]]:
    """Fallback: fetch PR unified diff directly from GitHub and parse file changes."""
    diff_url = f"https://github.com/{owner}/{repo}/pull/{number}.diff"
    request = urllib.request.Request(diff_url, headers={"Accept": "application/vnd.github.v3.diff"})
    token = os.getenv("LEADSYNC_GITHUB_TOKEN", "").strip() or os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - controlled URL format
        body = response.read().decode("utf-8", errors="replace")
    return _parse_unified_diff(body)


def list_pr_files(
    github_tools: list[Any],
    owner: str,
    repo: str,
    number: int,
    *,
    base_sha: str = "",
    head_sha: str = "",
) -> list[dict[str, Any]]:
    """Return normalized changed-file metadata for a pull request.

    Tries PR-files endpoint first, then falls back to commit compare
    (base...head) to cover cumulative branch changes.
    """
    tool = find_tool(
        github_tools,
        "GITHUB_LIST_PULL_REQUEST_FILES",
        "GITHUB_LIST_FILES_FOR_A_PULL_REQUEST",
        "GITHUB_LIST_FILES_ON_A_PULL_REQUEST",
    )
    if tool is not None:
        variants = [
            {"owner": owner, "repo": repo, "pull_number": number},
            {"owner": owner, "repo": repo, "number": number},
        ]
        try:
            response = run_tool_variants(tool, variants)
            plain = to_plain(response)
            normalized = _merge_files_by_path(_normalize_files(_extract_file_items(plain)))
            if normalized:
                return normalized
        except Exception:
            pass

    if base_sha and head_sha:
        compare_tool = find_tool(
            github_tools,
            "GITHUB_COMPARE_TWO_COMMITS",
            "GITHUB_COMPARE_COMMITS",
        )
        if compare_tool is not None:
            variants = [
                {"owner": owner, "repo": repo, "base": base_sha, "head": head_sha},
                {"owner": owner, "repo": repo, "basehead": f"{base_sha}...{head_sha}"},
                {"owner": owner, "repo": repo, "base_head": f"{base_sha}...{head_sha}"},
                {"owner": owner, "repo": repo, "base_ref": base_sha, "head_ref": head_sha},
            ]
            try:
                response = run_tool_variants(compare_tool, variants)
                plain = to_plain(response)
                normalized = _merge_files_by_path(_normalize_files(_extract_file_items(plain)))
                if normalized:
                    return normalized
            except Exception:
                pass

    commits_tool = find_tool(
        github_tools,
        "GITHUB_LIST_COMMITS_ON_A_PULL_REQUEST",
        "GITHUB_LIST_PULL_REQUEST_COMMITS",
    )
    commit_tool = find_tool(
        github_tools,
        "GITHUB_GET_A_COMMIT",
        "GITHUB_GET_A_COMMIT_OBJECT",
    )
    if commits_tool is not None and commit_tool is not None:
        commit_variants = [
            {"owner": owner, "repo": repo, "pull_number": number},
            {"owner": owner, "repo": repo, "number": number},
        ]
        try:
            commits_response = run_tool_variants(commits_tool, commit_variants)
            commits_plain = to_plain(commits_response)
            commit_items: list[Any] = commits_plain if isinstance(commits_plain, list) else _extract_file_items(commits_plain)
            shas: list[str] = []
            for item in commit_items:
                if not isinstance(item, dict):
                    continue
                sha = str(item.get("sha") or "").strip()
                if sha:
                    shas.append(sha)

            all_files: list[dict[str, Any]] = []
            for sha in shas:
                variants = [
                    {"owner": owner, "repo": repo, "ref": sha},
                    {"owner": owner, "repo": repo, "sha": sha},
                    {"owner": owner, "repo": repo, "commit_sha": sha},
                ]
                try:
                    commit_response = run_tool_variants(commit_tool, variants)
                except Exception:
                    continue
                commit_plain = to_plain(commit_response)
                all_files.extend(_normalize_files(_extract_file_items(commit_plain)))
            normalized = _merge_files_by_path(all_files)
            if normalized:
                return normalized
        except Exception:
            pass

    try:
        normalized = _fetch_pr_diff_http(owner, repo, number)
        if normalized:
            return normalized
    except Exception:
        pass

    return []


def upsert_pr_body(github_tools: list[Any], owner: str, repo: str, number: int, body: str) -> None:
    """Update pull request body using whichever update/edit tool is available."""
    tool = find_tool(
        github_tools,
        "GITHUB_UPDATE_A_PULL_REQUEST",
        "GITHUB_EDIT_A_PULL_REQUEST",
        "GITHUB_UPDATE_PULL_REQUEST",
    )
    if tool is None:
        raise RuntimeError("No GitHub pull request update tool available.")

    variants = [
        {"owner": owner, "repo": repo, "pull_number": number, "body": body},
        {"owner": owner, "repo": repo, "number": number, "body": body},
    ]
    run_tool_variants(tool, variants)
