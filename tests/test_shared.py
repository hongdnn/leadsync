"""
tests/test_shared.py
Unit tests for src/shared.py.
"""

import pytest
from unittest.mock import MagicMock, patch


def test_required_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SOME_MISSING_VAR", raising=False)
    from src.shared import _required_env
    with pytest.raises(RuntimeError, match="SOME_MISSING_VAR"):
        _required_env("SOME_MISSING_VAR")


def test_required_env_raises_when_blank(monkeypatch):
    monkeypatch.setenv("SOME_BLANK_VAR", "   ")
    from src.shared import _required_env
    with pytest.raises(RuntimeError, match="SOME_BLANK_VAR"):
        _required_env("SOME_BLANK_VAR")


def test_required_env_returns_value(monkeypatch):
    monkeypatch.setenv("MY_VAR", "hello")
    from src.shared import _required_env
    assert _required_env("MY_VAR") == "hello"


def test_required_gemini_api_key_prefers_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "legacy-key")
    from src.shared import _required_gemini_api_key
    assert _required_gemini_api_key() == "gemini-key"


def test_required_gemini_api_key_falls_back_to_legacy(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "legacy-key")
    from src.shared import _required_gemini_api_key
    assert _required_gemini_api_key() == "legacy-key"


def test_required_gemini_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from src.shared import _required_gemini_api_key
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        _required_gemini_api_key()


def test_build_llm_returns_default_when_unset(monkeypatch):
    monkeypatch.delenv("LEADSYNC_GEMINI_MODEL", raising=False)
    from src.shared import build_llm, DEFAULT_GEMINI_MODEL
    assert build_llm() == DEFAULT_GEMINI_MODEL


def test_build_llm_returns_custom_model(monkeypatch):
    monkeypatch.setenv("LEADSYNC_GEMINI_MODEL", "gemini/gemini-1.5-pro")
    from src.shared import build_llm
    assert build_llm() == "gemini/gemini-1.5-pro"


def test_build_tools_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)
    from src.shared import build_tools
    with pytest.raises(RuntimeError, match="COMPOSIO_API_KEY"):
        build_tools(user_id="default", toolkits=["JIRA"])


def test_build_tools_returns_tool_list(monkeypatch):
    monkeypatch.setenv("COMPOSIO_API_KEY", "fake-key")
    fake_tools = [MagicMock(), MagicMock()]
    mock_composio_instance = MagicMock()
    mock_composio_instance.tools.get.return_value = fake_tools

    with patch.dict("sys.modules", {
        "composio": MagicMock(Composio=MagicMock(return_value=mock_composio_instance)),
        "composio_crewai": MagicMock(CrewAIProvider=MagicMock()),
    }):
        from src.shared import build_tools
        result = build_tools(user_id="default", toolkits=["JIRA", "SLACK"])

    assert result == fake_tools
    mock_composio_instance.tools.get.assert_called_once_with(
        user_id="default", toolkits=["JIRA", "SLACK"], limit=200
    )


def test_crew_run_result_dataclass():
    from src.shared import CrewRunResult
    result = CrewRunResult(raw="some output", model="gemini/gemini-2.5-flash")
    assert result.raw == "some output"
    assert result.model == "gemini/gemini-2.5-flash"
