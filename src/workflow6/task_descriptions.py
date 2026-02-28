"""
Workflow 6 agent task descriptions.
Exports: scan_description, summarize_description
"""


def scan_description(
    issue_key: str,
    summary: str,
    description: str,
    repo_owner: str,
    repo_name: str,
) -> str:
    """Return task description for the Implementation Scanner agent.

    Args:
        issue_key: Jira issue key (e.g. LEADS-99).
        summary: Ticket summary text.
        description: Ticket description text.
        repo_owner: GitHub repository owner.
        repo_name: GitHub repository name.
    Returns:
        Task description string.
    """
    desc_snippet = description[:200] if description else "N/A"
    return (
        f"Search the main branch of {repo_owner}/{repo_name} for code changes "
        f"that implemented Jira ticket {issue_key}.\n\n"
        "PHASE 1 — Recent commits and merged PRs (last 24 hours):\n"
        f"- List commits on main from the last 24 hours and look for messages containing '{issue_key}'.\n"
        f"- List merged PRs whose title or body contains '{issue_key}'.\n"
        "- For each matching commit or PR, list the files changed with additions/deletions.\n"
        f"- If no exact key matches, broaden: search using keywords from the summary: {summary}\n"
        f"  and from the description: {desc_snippet}\n\n"
        "PHASE 2 — File-based fallback (only if Phase 1 found nothing):\n"
        "- Use the repository tree to browse the directory structure.\n"
        "- Identify files/directories whose names relate to the ticket summary or description.\n"
        f"- Read the content of up to 5 candidate files that most likely contain the functionality described in: {summary}\n"
        "- For each file, note its path and a brief description of what it contains.\n\n"
        "Output format:\n"
        "If Phase 1 found results (one line per finding):\n"
        "COMMIT: <sha> | MSG: <message> | FILES: <file1>, <file2>, ...\n"
        "PR: #<number> | TITLE: <title> | FILES: <file1>, <file2>, ...\n\n"
        "If only Phase 2 produced results:\n"
        "REPO_FILE: <path> | DESCRIPTION: <what this file contains>\n\n"
        "If neither phase found anything, output: NO_MATCHES_FOUND"
    )


def summarize_description(issue_key: str, summary: str) -> str:
    """Return task description for the Implementation Summarizer agent.

    Args:
        issue_key: Jira issue key.
        summary: Ticket summary text.
    Returns:
        Task description string.
    """
    return (
        f"Read the scanner's findings about ticket {issue_key} ({summary}).\n\n"
        "Steps:\n"
        "- Map the found files and changes to the ticket requirements.\n"
        "- Identify the key areas of the codebase that were modified or that contain relevant functionality.\n"
        "- If findings came from commits/PRs, summarize what was changed.\n"
        "- If findings came from the file-based fallback (REPO_FILE entries), describe "
        "which files likely contain the implemented functionality and what they do.\n"
        "- Produce a plain-text implementation summary (no markdown).\n\n"
        "Output format:\n"
        "IMPLEMENTATION_SUMMARY: <2-3 sentences describing what was implemented or where the functionality lives>\n"
        "FILES_CHANGED: <file1>, <file2>, ...\n\n"
        "If the scanner found no matches, output:\n"
        "IMPLEMENTATION_SUMMARY: No matching commits, PRs, or relevant files found for this ticket.\n"
        "FILES_CHANGED: none"
    )
