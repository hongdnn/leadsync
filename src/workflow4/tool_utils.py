"""Workflow 4 Composio tool discovery and invocation helpers."""

from typing import Any


def to_plain(value: Any) -> Any:
    """Best-effort normalize SDK objects into plain dict/list primitives."""
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_plain(v) for v in value]
    if hasattr(value, "model_dump"):
        return to_plain(value.model_dump())
    if hasattr(value, "dict"):
        return to_plain(value.dict())
    if hasattr(value, "__dict__"):
        return to_plain(vars(value))
    return value


def _tool_name(tool: Any) -> str:
    """Return uppercased name attribute from a Composio tool object."""
    return str(getattr(tool, "name", "")).upper()


def find_tool(tools: list[Any], *names: str) -> Any | None:
    """Find first tool whose name matches one of the provided names."""
    want = {name.upper() for name in names}
    for tool in tools:
        if _tool_name(tool) in want:
            return tool
    return None


def run_tool_variants(tool: Any, variants: list[dict[str, Any]]) -> Any:
    """Run a tool with argument variants and return first successful response."""
    last_err: Exception | None = None
    for args in variants:
        try:
            return tool.run(**args)
        except Exception as exc:  # pragma: no cover - external SDK variability
            last_err = exc
    if last_err:
        raise last_err
    raise RuntimeError("No argument variants supplied for tool call.")
