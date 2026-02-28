from typing import Any

from src.config import Config
from src.integrations.composio_provider import get_composio_tools

REQUIRED_JIRA_TOOLS = [
    "JIRA_GET_ISSUE",
    "JIRA_EDIT_ISSUE",
    "JIRA_ADD_COMMENT",
    "JIRA_ADD_ATTACHMENT",
    "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST",
]


def get_agent_tools() -> list[Any]:
    # Request Jira tools explicitly to avoid truncated/default toolkit tool lists.
    toolkits = ["GITHUB"] if Config.github_enabled() else None
    return get_composio_tools(
        user_id=Config.get_composio_user_id(),
        tools=REQUIRED_JIRA_TOOLS,
        toolkits=toolkits,
    )
