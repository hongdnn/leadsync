"""Unit tests for Workflow 1 key-file parsing and formatting helpers."""

from src.workflow1.key_files import format_key_files_markdown, parse_key_files


def test_parse_key_files_extracts_and_caps_results():
    text = "\n".join(
        [
            "KEY_FILE: src/a.py | WHY: A | CONFIDENCE: high",
            "KEY_FILE: src/b.py | WHY: B | CONFIDENCE: medium",
            "KEY_FILE: src/c.py | WHY: C | CONFIDENCE: low",
        ]
    )
    parsed = parse_key_files(text, limit=2)
    assert len(parsed) == 2
    assert parsed[0].path == "src/a.py"
    assert parsed[1].path == "src/b.py"


def test_parse_key_files_dedupes_and_normalizes_confidence():
    text = "\n".join(
        [
            "KEY_FILE: src/A.py | WHY: First | CONFIDENCE: HIGH",
            "KEY_FILE: src/a.py | WHY: Duplicate | CONFIDENCE: weird",
        ]
    )
    parsed = parse_key_files(text, limit=8)
    assert len(parsed) == 1
    assert parsed[0].confidence == "high"


def test_format_key_files_markdown_renders_expected_lines():
    text = "KEY_FILE: src/auth.py | WHY: Route wiring | CONFIDENCE: high"
    parsed = parse_key_files(text)
    rendered = format_key_files_markdown(parsed)
    assert "`src/auth.py`" in rendered
    assert "Route wiring" in rendered
    assert "confidence: high" in rendered
