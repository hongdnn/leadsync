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
    summary_snippet = summary[:100] if summary else "N/A"
    return (
        f"Find recent commits on {repo_owner}/{repo_name} related to Jira ticket {issue_key}.\n\n"
        "Steps:\n"
        f"1. List commits on main and look for messages containing '{issue_key}' or '{summary_snippet}'.\n"
        "2. For each match, note the SHA, message, and files changed.\n"
        "3. If no commits match, output NO_MATCHES_FOUND.\n\n"
        "Output one line per finding:\n"
        "COMMIT: <sha> | MSG: <message> | FILES: <file1>, <file2>, ...\n\n"
        "If nothing found: NO_MATCHES_FOUND"
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
