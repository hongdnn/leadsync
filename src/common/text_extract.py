"""Best-effort plain text extraction from nested Jira/Composio payloads."""

from typing import Any


def extract_text(value: Any, *, joiner: str = " ") -> str:
    """
    Extract plain text from string/list/dict trees.

    Args:
        value: Arbitrary nested payload object.
        joiner: Joiner used for list/dict flattened text.
    Returns:
        Extracted text string.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [extract_text(item, joiner=joiner) for item in value]
        return joiner.join(part for part in parts if part)
    if isinstance(value, dict):
        text_value = value.get("text")
        if isinstance(text_value, str):
            return text_value.strip()
        for key in ("plain_text", "plaintext", "content", "result", "data", "response"):
            if key in value:
                candidate = extract_text(value.get(key), joiner=joiner)
                if candidate:
                    return candidate
        nested = [extract_text(item, joiner=joiner) for item in value.values()]
        return joiner.join(part for part in nested if part)
    return ""
