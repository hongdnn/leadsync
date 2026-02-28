"""Backward-compatible Composio provider facade for legacy tool callers."""

from typing import Any

from src.shared import build_tools


def get_composio_tools(
    user_id: str,
    tools: list[str] | None = None,
    toolkits: list[str] | None = None,
) -> list[Any]:
    """Return Composio tools using the shared tool builder."""
    return build_tools(user_id=user_id, toolkits=toolkits, tools=tools)
