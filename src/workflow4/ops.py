"""Workflow 4 tool operations for PR auto-description."""

from typing import Any


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


def list_pr_files(github_tools: list[Any], owner: str, repo: str, number: int) -> list[dict[str, Any]]:
    """Return normalized changed-file metadata for a pull request."""
    tool = find_tool(
        github_tools,
        "GITHUB_LIST_PULL_REQUEST_FILES",
        "GITHUB_LIST_FILES_FOR_A_PULL_REQUEST",
        "GITHUB_LIST_FILES_ON_A_PULL_REQUEST",
    )
    if tool is None:
        return []

    variants = [
        {"owner": owner, "repo": repo, "pull_number": number},
        {"owner": owner, "repo": repo, "number": number},
    ]
    response = run_tool_variants(tool, variants)
    plain = to_plain(response)

    items: list[Any] = []
    if isinstance(plain, list):
        items = plain
    elif isinstance(plain, dict):
        for key in ("files", "data", "items", "pull_request_files"):
            value = plain.get(key)
            if isinstance(value, list):
                items = value
                break

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
            }
        )
    return normalized


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
