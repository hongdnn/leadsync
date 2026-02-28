"""
src/prefs.py
Google Docs-backed tech lead preference resolution and loading helpers.
Exports: resolve_preference_category, resolve_doc_id, load_preferences_for_category, append_preference
"""

from src.common.prefs_core import (
    PREF_CATEGORY_BACKEND,
    PREF_CATEGORY_DATABASE,
    PREF_CATEGORY_FRONTEND,
    load_preferences_for_category,
    resolve_doc_id,
    resolve_preference_category,
)


def append_preference(text: str) -> None:
    """
    Deprecated preference mutation entrypoint.

    Args:
        text: Ignored; retained for backward compatibility.
    Raises:
        RuntimeError: Always, because Google Docs is the only supported source.
    """
    del text
    raise RuntimeError(
        "append_preference is deprecated. Preferences now come from Google Docs only."
    )


__all__ = [
    "PREF_CATEGORY_FRONTEND",
    "PREF_CATEGORY_BACKEND",
    "PREF_CATEGORY_DATABASE",
    "resolve_preference_category",
    "resolve_doc_id",
    "load_preferences_for_category",
    "append_preference",
]
