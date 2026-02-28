"""
src/shared.py
Shared utilities for all LeadSync crew files.
Exports: _required_env, build_llm, build_tools, CrewRunResult
"""

import os
from dataclasses import dataclass
from typing import Any

DEFAULT_GEMINI_MODEL = "gemini/gemini-2.5-flash"


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


def build_tools(user_id: str, toolkits: list[str]) -> list[Any]:
    """
    Build Composio tool list for CrewAI agents.

    Args:
        user_id: Composio user identifier.
        toolkits: List of toolkit names e.g. ['JIRA', 'SLACK'].
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
    return composio.tools.get(user_id=user_id, toolkits=toolkits)
