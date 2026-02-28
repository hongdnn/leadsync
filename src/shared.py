"""
src/shared.py
Shared utilities for all LeadSync crew files.
Exports: _required_env, _required_gemini_api_key, build_llm, build_tools, CrewRunResult
"""

import os
from dataclasses import dataclass
from typing import Any

DEFAULT_GEMINI_MODEL = "gemini/gemini-2.5-flash"
DEFAULT_TOOL_LIMIT = 200


@dataclass
class CrewRunResult:
    """Return type for all crew run functions."""
    raw: str
    model: str


def _required_env(name: str) -> str:
    """
    Read a required environment variable.

    Args:
        name: The environment variable name.
    Returns:
        The stripped string value.
    Raises:
        RuntimeError: If the variable is absent or blank.
    """
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _required_gemini_api_key() -> str:
    """
    Read the required Gemini API key with legacy fallback support.

    Returns:
        Gemini API key value.
    Raises:
        RuntimeError: If neither GEMINI_API_KEY nor GOOGLE_API_KEY is set.
    """
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        return gemini_key
    legacy_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if legacy_key:
        return legacy_key
    raise RuntimeError("Missing required env var: GEMINI_API_KEY (or GOOGLE_API_KEY)")


def build_llm() -> str:
    """
    Return the configured Gemini model name.

    Reads LEADSYNC_GEMINI_MODEL from env.
    Returns:
        Model name string (e.g. 'gemini/gemini-2.5-flash').
    Side effects:
        None.
    """
    return os.getenv("LEADSYNC_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)


def build_tools(user_id: str, toolkits: list[str], limit: int = DEFAULT_TOOL_LIMIT) -> list[Any]:
    """
    Build Composio tool list for CrewAI agents.

    Args:
        user_id: Composio user identifier.
        toolkits: List of toolkit names e.g. ['JIRA', 'SLACK'].
        limit: Max number of tool definitions returned by Composio.
    Returns:
        List of CrewAI-compatible tool objects.
    Side effects:
        Sets COMPOSIO_CACHE_DIR env default. Validates COMPOSIO_API_KEY present.
    Raises:
        RuntimeError: If COMPOSIO_API_KEY is not set.
    """
    _required_env("COMPOSIO_API_KEY")
    os.environ.setdefault("COMPOSIO_CACHE_DIR", ".composio-cache")
    from composio import Composio
    from composio_crewai import CrewAIProvider

    composio = Composio(provider=CrewAIProvider())
    return composio.tools.get(user_id=user_id, toolkits=toolkits, limit=limit)
