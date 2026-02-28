import os
from typing import Any

from src.config import Config


def get_composio_tools(
    user_id: str, tools: list[str] | None = None, toolkits: list[str] | None = None
) -> list[Any]:
    Config.require_env("COMPOSIO_API_KEY")
    os.environ.setdefault("COMPOSIO_CACHE_DIR", ".composio-cache")
    from composio import Composio
    from composio_crewai import CrewAIProvider

    composio = Composio(provider=CrewAIProvider())
    kwargs: dict[str, Any] = {"user_id": user_id}
    if tools:
        kwargs["tools"] = tools
    if toolkits:
        kwargs["toolkits"] = toolkits
    return composio.tools.get(**kwargs)
