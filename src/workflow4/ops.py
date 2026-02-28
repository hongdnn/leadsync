"""Workflow 4 high-level PR operations: file listing and body update."""

from typing import Any

from src.workflow4.diff_parser import (
    _extract_file_items,
    _merge_files_by_path,
    _normalize_files,
    fetch_pr_diff_http,
)
from src.workflow4.tool_utils import find_tool, run_tool_variants, to_plain


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

    Tries multiple strategies in order:
    1. PR-files endpoint
    2. Commit compare (base...head)
    3. Individual commit file lists
    4. Raw .diff HTTP fallback
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
        normalized = fetch_pr_diff_http(owner, repo, number)
        if normalized:
            return normalized
    except Exception:
        pass

    return []


def upsert_pr_body(
    github_tools: list[Any], owner: str, repo: str, number: int, body: str, *, title: str = ""
) -> None:
    """Update pull request body and optionally title using whichever update/edit tool is available."""
    tool = find_tool(
        github_tools,
        "GITHUB_UPDATE_A_PULL_REQUEST",
        "GITHUB_EDIT_A_PULL_REQUEST",
        "GITHUB_UPDATE_PULL_REQUEST",
    )
    if tool is None:
        raise RuntimeError("No GitHub pull request update tool available.")

    base_a: dict[str, Any] = {"owner": owner, "repo": repo, "pull_number": number, "body": body}
    base_b: dict[str, Any] = {"owner": owner, "repo": repo, "number": number, "body": body}
    if title:
        base_a["title"] = title
        base_b["title"] = title

    variants = [base_a, base_b]
    run_tool_variants(tool, variants)

    # If title was provided but the combined call might have silently ignored it,
    # make a dedicated title-only update as a fallback.
    if title:
        try:
            title_variants = [
                {"owner": owner, "repo": repo, "pull_number": number, "title": title},
                {"owner": owner, "repo": repo, "number": number, "title": title},
            ]
            run_tool_variants(tool, title_variants)
        except Exception:
            pass  # Best-effort; body update already succeeded above.
