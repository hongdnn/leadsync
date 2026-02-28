"""
tests/test_prefs.py
Unit tests for src/prefs.py — tech lead preferences loader and appender.
"""

import pytest
from unittest.mock import patch


def test_load_preferences_returns_file_content(tmp_path):
    from src import prefs
    prefs_file = tmp_path / "tech-lead-context.md"
    prefs_file.write_text("# Preferences\n- Prefer async.")
    with patch("src.prefs.TECH_LEAD_CONTEXT_PATH", prefs_file):
        result = prefs.load_preferences()
    assert "Prefer async" in result


def test_load_preferences_raises_runtime_error_when_file_missing(tmp_path):
    from src import prefs
    missing = tmp_path / "nonexistent.md"
    with patch("src.prefs.TECH_LEAD_CONTEXT_PATH", missing):
        with pytest.raises(RuntimeError, match="preferences file missing"):
            prefs.load_preferences()


def test_append_preference_creates_section_when_absent(tmp_path):
    from src import prefs
    prefs_file = tmp_path / "tech-lead-context.md"
    prefs_file.write_text("# Existing Content\n- Some rule.\n")
    with patch("src.prefs.TECH_LEAD_CONTEXT_PATH", prefs_file):
        prefs.append_preference("Always wrap DB calls in transactions")
    content = prefs_file.read_text()
    assert "## Quick Rules (added via Slack)" in content
    assert "Always wrap DB calls in transactions" in content


def test_append_preference_adds_to_existing_section(tmp_path):
    from src import prefs
    prefs_file = tmp_path / "tech-lead-context.md"
    prefs_file.write_text(
        "# Existing Content\n\n## Quick Rules (added via Slack)\n\n- First rule.\n"
    )
    with patch("src.prefs.TECH_LEAD_CONTEXT_PATH", prefs_file):
        prefs.append_preference("Second rule here")
    content = prefs_file.read_text()
    assert content.count("## Quick Rules (added via Slack)") == 1
    assert "Second rule here" in content


def test_append_preference_does_not_duplicate_section_header(tmp_path):
    from src import prefs
    prefs_file = tmp_path / "tech-lead-context.md"
    prefs_file.write_text(
        "## Quick Rules (added via Slack)\n\n- Rule one.\n"
    )
    with patch("src.prefs.TECH_LEAD_CONTEXT_PATH", prefs_file):
        prefs.append_preference("Rule two")
        prefs.append_preference("Rule three")
    content = prefs_file.read_text()
    assert content.count("## Quick Rules (added via Slack)") == 1
    assert "Rule two" in content
    assert "Rule three" in content


def test_append_preference_raises_on_empty_text(tmp_path):
    from src import prefs
    prefs_file = tmp_path / "tech-lead-context.md"
    prefs_file.write_text("# Content\n")
    with patch("src.prefs.TECH_LEAD_CONTEXT_PATH", prefs_file):
        with pytest.raises(ValueError, match="empty"):
            prefs.append_preference("   ")
