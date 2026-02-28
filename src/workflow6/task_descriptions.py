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
    return (
        f"Search the main branch of {repo_owner}/{repo_name} for code changes "
        f"that implemented Jira ticket {issue_key}.\n\n"
        "Steps:\n"
        f"- Search main branch commits for messages containing '{issue_key}'.\n"
        f"- List merged PRs whose title or body contains '{issue_key}'.\n"
        "- For each matching commit or PR, list the files changed with additions/deletions.\n"
        f"- If no exact key matches are found, search using keywords from the summary: {summary}\n"
        f"- And from the description: {description[:200] if description else 'N/A'}\n\n"
        "Output format (one line per finding):\n"
        "COMMIT: <sha> | MSG: <message> | FILES: <file1>, <file2>, ...\n"
        "PR: #<number> | TITLE: <title> | FILES: <file1>, <file2>, ...\n\n"
        "If no commits or PRs are found, output: NO_MATCHES_FOUND"
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
        "- Identify the key areas of the codebase that were modified.\n"
        "- Produce a plain-text implementation summary (no markdown).\n\n"
        "Output format:\n"
        "IMPLEMENTATION_SUMMARY: <2-3 sentences describing what was implemented>\n"
        "FILES_CHANGED: <file1>, <file2>, ...\n\n"
        "If the scanner found no matches, output:\n"
        "IMPLEMENTATION_SUMMARY: No matching commits or PRs found for this ticket.\n"
        "FILES_CHANGED: none"
    )
