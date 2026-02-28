"""Core Google Docs-backed tech lead preference helpers."""

import logging
from typing import Any

from src.common.text_extract import extract_text
from src.common.token_matching import normalize_tokens
from src.common.tool_helpers import find_tool_by_name
from src.shared import _required_env

logger = logging.getLogger(__name__)

PREF_CATEGORY_FRONTEND = "frontend"
PREF_CATEGORY_BACKEND = "backend"
PREF_CATEGORY_DATABASE = "database"
DOC_PLAINTEXT_TOOL = "GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT"

DOC_ID_ENV_BY_CATEGORY = {
    PREF_CATEGORY_FRONTEND: "LEADSYNC_FRONTEND_PREFS_DOC_ID",
    PREF_CATEGORY_BACKEND: "LEADSYNC_BACKEND_PREFS_DOC_ID",
    PREF_CATEGORY_DATABASE: "LEADSYNC_DATABASE_PREFS_DOC_ID",
}

CATEGORY_KEYWORDS: list[tuple[str, set[str]]] = [
    (PREF_CATEGORY_FRONTEND, {"frontend", "front", "ui", "ux", "fe", "client", "react", "web"}),
    (PREF_CATEGORY_DATABASE, {"database", "db", "sql", "schema", "migration", "postgres", "query"}),
    (PREF_CATEGORY_BACKEND, {"backend", "back", "api", "service", "be", "server"}),
]


def resolve_preference_category(labels: list[str], component_names: list[str]) -> str:
    """Resolve preference category from Jira labels/components."""
    tokens = normalize_tokens(labels) + normalize_tokens(component_names)
    for category, keywords in CATEGORY_KEYWORDS:
        if any(token in keywords for token in tokens):
            return category
    return PREF_CATEGORY_BACKEND


def resolve_doc_id(category: str) -> str:
    """Resolve required Google Doc ID env var for a category."""
    env_name = DOC_ID_ENV_BY_CATEGORY.get(category)
    if not env_name:
        raise RuntimeError(f"Unknown preference category: {category}")
    return _required_env(env_name)


def load_preferences_for_category(category: str, docs_tools: list[Any]) -> str:
    """Load category preference text from Google Docs plaintext tool."""
    doc_id = resolve_doc_id(category)
    tool = find_tool_by_name(docs_tools, DOC_PLAINTEXT_TOOL)
    if tool is None:
        raise RuntimeError(f"{DOC_PLAINTEXT_TOOL} tool is required for Google Docs preferences.")
    try:
        response = tool.run(document_id=doc_id)
    except Exception as exc:
        logger.exception("Google Docs preference fetch failed for category '%s'.", category)
        raise RuntimeError(f"Failed to fetch Google Docs preferences for {category}: {exc}") from exc
    text = extract_text(response, joiner="\n")
    if not text.strip():
        raise RuntimeError(f"Google Docs preferences for {category} are empty.")
    return text.strip()
