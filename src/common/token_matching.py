"""Token normalization helpers for label/component keyword matching."""

import re


def normalize_tokens(values: list[str]) -> list[str]:
    """
    Normalize mixed label/component strings to search tokens.

    Args:
        values: Raw tokens from Jira labels/components.
    Returns:
        Lowercase expanded token list.
    """
    tokens: list[str] = []
    for value in values:
        lowered = str(value).strip().lower()
        if not lowered:
            continue
        tokens.append(lowered)
        tokens.extend(token for token in re.split(r"[^a-z0-9]+", lowered) if token)
    return tokens
