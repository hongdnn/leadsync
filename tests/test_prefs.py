"""
tests/test_prefs.py
Unit tests for src/prefs.py — Google Docs-backed team preferences.
"""

import pytest
from unittest.mock import MagicMock


def test_resolve_preference_category_frontend_from_label():
    from src.prefs import resolve_preference_category

    category = resolve_preference_category(labels=["frontend"], component_names=[])
    assert category == "frontend"


def test_resolve_preference_category_database_from_component():
    from src.prefs import resolve_preference_category

    category = resolve_preference_category(labels=[], component_names=["db-migrations"])
    assert category == "database"


def test_resolve_preference_category_defaults_to_backend():
    from src.prefs import resolve_preference_category

    category = resolve_preference_category(labels=["priority-high"], component_names=["ops"])
    assert category == "backend"


def test_resolve_doc_id_uses_required_env(monkeypatch):
    from src.prefs import resolve_doc_id

    monkeypatch.setenv("LEADSYNC_BACKEND_PREFS_DOC_ID", "doc-123")
    assert resolve_doc_id("backend") == "doc-123"


def test_resolve_doc_id_raises_for_missing_env(monkeypatch):
    from src.prefs import resolve_doc_id

    monkeypatch.delenv("LEADSYNC_FRONTEND_PREFS_DOC_ID", raising=False)
    with pytest.raises(RuntimeError, match="LEADSYNC_FRONTEND_PREFS_DOC_ID"):
        resolve_doc_id("frontend")


def test_load_preferences_for_category_reads_google_doc_plaintext(monkeypatch):
    from src.prefs import load_preferences_for_category

    monkeypatch.setenv("LEADSYNC_DATABASE_PREFS_DOC_ID", "db-doc-1")
    tool = MagicMock()
    tool.name = "GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT"
    tool.run.return_value = {"plain_text": "Prefer additive migrations.\nAlways write rollback."}

    result = load_preferences_for_category(category="database", docs_tools=[tool])

    tool.run.assert_called_once_with(document_id="db-doc-1")
    assert "Prefer additive migrations" in result


def test_load_preferences_for_category_raises_when_tool_missing(monkeypatch):
    from src.prefs import load_preferences_for_category

    monkeypatch.setenv("LEADSYNC_BACKEND_PREFS_DOC_ID", "be-doc-1")
    with pytest.raises(RuntimeError, match="GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT"):
        load_preferences_for_category(category="backend", docs_tools=[])


def test_load_preferences_for_category_raises_on_empty_doc_text(monkeypatch):
    from src.prefs import load_preferences_for_category

    monkeypatch.setenv("LEADSYNC_FRONTEND_PREFS_DOC_ID", "fe-doc-1")
    tool = MagicMock()
    tool.name = "GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT"
    tool.run.return_value = {"plain_text": "   "}

    with pytest.raises(RuntimeError, match="empty"):
        load_preferences_for_category(category="frontend", docs_tools=[tool])


def test_append_preference_is_deprecated():
    from src.prefs import append_preference

    with pytest.raises(RuntimeError, match="deprecated"):
        append_preference("any")
