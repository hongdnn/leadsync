"""Shared helpers for evaluating tool call responses."""

from typing import Any

from src.common.text_extract import extract_text

_FAILURE_STATUS = {"error", "failed", "failure"}
_FAILURE_TOKENS = {"error", "failed", "forbidden", "unauthorized", "not found", "exception"}


def response_indicates_failure(response: Any) -> bool:
    """Return whether a tool response payload appears to represent failure."""
    if response is None:
        return True
    if isinstance(response, dict):
        if "successful" in response and response.get("successful") is False:
            return True
        if "success" in response and response.get("success") is False:
            return True
        status = str(response.get("status", "")).strip().lower()
        if status in _FAILURE_STATUS:
            return True
        if response.get("error") or response.get("errors"):
            return True
    text = extract_text(response, joiner=" ").strip().lower()
    if not text:
        return False
    if "no error" in text:
        return False
    return any(token in text for token in _FAILURE_TOKENS)


def summarize_tool_response(response: Any, max_chars: int = 280) -> str:
    """Return a compact, readable summary for logs and error messages."""
    text = extract_text(response, joiner=" ").strip()
    if not text:
        text = str(response)
    return text if len(text) <= max_chars else f"{text[: max_chars - 3]}..."

