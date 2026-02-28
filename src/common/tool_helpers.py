"""Tool lookup and tool-name inspection helpers."""

from typing import Any


def find_tool_by_name(tools: list[Any], name: str) -> Any | None:
    """
    Return first tool with exact uppercased `name`.

    Args:
        tools: Tool list.
        name: Expected tool name.
    Returns:
        Matching tool or None.
    """
    expected = name.upper()
    for tool in tools:
        if getattr(tool, "name", "").upper() == expected:
            return tool
    return None


def tool_name_set(tools: list[Any]) -> set[str]:
    """Return uppercased tool-name set."""
    return {getattr(tool, "name", "").upper() for tool in tools}


def has_tool_prefix(tool_names: set[str], prefix: str) -> bool:
    """Return whether any tool name starts with prefix."""
    upper = prefix.upper()
    return any(name.startswith(upper) for name in tool_names)
