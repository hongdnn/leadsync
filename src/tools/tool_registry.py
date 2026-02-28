"""
src/tools/tool_registry.py
Central registry of explicit Composio tool names per workflow.

Each workflow declares exactly the tools its agents need, keeping
LLM context small and tool selection deterministic.
"""

# ---------------------------------------------------------------------------
# JIRA tools (shared across workflows)
# ---------------------------------------------------------------------------
WF1_JIRA_TOOLS: list[str] = [
    "JIRA_GET_ISSUE",
    "JIRA_EDIT_ISSUE",
    "JIRA_ADD_COMMENT",
    "JIRA_ADD_ATTACHMENT",
    "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST",
]

WF3_JIRA_TOOLS: list[str] = [
    "JIRA_GET_ISSUE",
    "JIRA_LIST_ISSUE_COMMENTS",
]

WF5_JIRA_TOOLS: list[str] = [
    "JIRA_GET_ISSUE",
    "JIRA_ADD_COMMENT",
    "JIRA_GET_TRANSITIONS",
    "JIRA_TRANSITION_ISSUE",
]

WF6_JIRA_TOOLS: list[str] = [
    "JIRA_GET_ISSUE",
    "JIRA_ADD_COMMENT",
]

# ---------------------------------------------------------------------------
# GITHUB tools
# ---------------------------------------------------------------------------
# WF1 Context Gatherer: search code, browse repo tree, list recent commits
WF1_GITHUB_TOOLS: list[str] = [
    "GITHUB_GET_REPOSITORY_CONTENT",
    "GITHUB_GET_RAW_REPOSITORY_CONTENT",
    "GITHUB_GET_A_TREE",
    "GITHUB_LIST_COMMITS",
    "GITHUB_GET_A_COMMIT",
    "GITHUB_FIND_PULL_REQUESTS",
    "GITHUB_GET_A_REPOSITORY_README",
]

# WF2 GitHub Scanner: list repo commits filtered by timestamp
WF2_GITHUB_TOOLS: list[str] = [
    "GITHUB_LIST_COMMITS",
    "GITHUB_GET_A_COMMIT",
]

# WF4 PR Auto-Description: read PR files, commits, update PR body
WF4_GITHUB_TOOLS: list[str] = [
    "GITHUB_LIST_PULL_REQUEST_FILES",
    "GITHUB_LIST_FILES_FOR_A_PULL_REQUEST",
    "GITHUB_LIST_FILES_ON_A_PULL_REQUEST",
    "GITHUB_COMPARE_TWO_COMMITS",
    "GITHUB_COMPARE_COMMITS",
    "GITHUB_LIST_COMMITS_ON_A_PULL_REQUEST",
    "GITHUB_LIST_PULL_REQUEST_COMMITS",
    "GITHUB_GET_A_COMMIT",
    "GITHUB_GET_A_COMMIT_OBJECT",
    "GITHUB_UPDATE_A_PULL_REQUEST",
    "GITHUB_EDIT_A_PULL_REQUEST",
    "GITHUB_UPDATE_PULL_REQUEST",
]

# WF5 Jira-PR Link: comment on GitHub PR
WF5_GITHUB_TOOLS: list[str] = [
    "GITHUB_CREATE_AN_ISSUE_COMMENT",
]

# WF6 Implementation Scanner: find commits/PRs matching ticket key,
# plus repo browsing for file-based fallback when no commits/PRs found.
WF6_GITHUB_TOOLS: list[str] = [
    "GITHUB_LIST_COMMITS",
    "GITHUB_GET_A_COMMIT",
    "GITHUB_FIND_PULL_REQUESTS",
    "GITHUB_GET_A_PULL_REQUEST",
    "GITHUB_LIST_PULL_REQUEST_FILES",
    "GITHUB_GET_REPOSITORY_CONTENT",
    "GITHUB_GET_A_TREE",
]

# ---------------------------------------------------------------------------
# SLACK tools
# ---------------------------------------------------------------------------
WF2_SLACK_TOOLS: list[str] = [
    "SLACK_SEND_MESSAGE",
]

WF3_SLACK_TOOLS: list[str] = [
    "SLACK_SEND_MESSAGE",
]

# ---------------------------------------------------------------------------
# GOOGLEDOCS tools (used pre-crew for preference loading)
# ---------------------------------------------------------------------------
GOOGLEDOCS_PREFS_TOOLS: list[str] = [
    "GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT",
    "GOOGLEDOCS_GET_DOCUMENT_BY_ID",
]
