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
DEFAULT_MEMORY_DB_PATH = "data/leadsync.db"
DEFAULT_DIGEST_WINDOW_MINUTES = 60


@dataclass
class CrewRunResult:
    """Return type for all crew run functions."""

    raw: str
    model: str


def _required_env(name: str) -> str:
    """Read a required environment variable or raise RuntimeError."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _required_gemini_api_key() -> str:
    """Return GEMINI_API_KEY, with GOOGLE_API_KEY legacy fallback."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        return gemini_key
    legacy_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if legacy_key:
        return legacy_key
    raise RuntimeError("Missing required env var: GEMINI_API_KEY (or GOOGLE_API_KEY)")


def build_llm() -> str:
    """Return configured Gemini model name."""
    return os.getenv("LEADSYNC_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)


def composio_user_id() -> str:
    """Return configured Composio user id with default fallback."""
    return os.getenv("COMPOSIO_USER_ID", "default")


def build_memory_db_path() -> str:
    """Return configured SQLite path for LeadSync memory."""
    return os.getenv("LEADSYNC_MEMORY_DB_PATH", DEFAULT_MEMORY_DB_PATH)


def build_digest_window_minutes() -> int:
    """Return configured digest lookback window (positive integer minutes)."""
    raw_value = os.getenv(
        "LEADSYNC_DIGEST_WINDOW_MINUTES", str(DEFAULT_DIGEST_WINDOW_MINUTES)
    ).strip()
    try:
        minutes = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            "Invalid LEADSYNC_DIGEST_WINDOW_MINUTES: expected a positive integer."
        ) from exc
    if minutes <= 0:
        raise RuntimeError(
            "Invalid LEADSYNC_DIGEST_WINDOW_MINUTES: expected a positive integer."
        )
    return minutes


def memory_enabled() -> bool:
    """Return whether memory subsystem is enabled."""
    value = os.getenv("LEADSYNC_MEMORY_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def digest_idempotency_enabled() -> bool:
    """Return whether digest idempotency locking is enabled."""
    value = os.getenv("LEADSYNC_DIGEST_IDEMPOTENCY_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def build_tools(
    user_id: str,
    toolkits: list[str] | None = None,
    *,
    tools: list[str] | None = None,
    limit: int = DEFAULT_TOOL_LIMIT,
) -> list[Any]:
    """Build Composio tool list for CrewAI agents."""
    _required_env("COMPOSIO_API_KEY")
    os.environ.setdefault("COMPOSIO_CACHE_DIR", ".composio-cache")
    from composio import Composio
    from composio_crewai import CrewAIProvider

    composio = Composio(provider=CrewAIProvider())
    kwargs: dict[str, Any] = {"user_id": user_id, "limit": limit}
    if toolkits:
        kwargs["toolkits"] = toolkits
    if tools:
        kwargs["tools"] = tools
    return composio.tools.get(**kwargs)
