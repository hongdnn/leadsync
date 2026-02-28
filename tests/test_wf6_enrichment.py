"""Tests for WF6 implementation detail enrichment in same-label history."""

from unittest.mock import MagicMock

from src.common.jira_history_parse import (
    HistoryTicket,
    extract_wf6_implementation,
)


# -- extract_wf6_implementation tests -----------------------------------------

WF6_RESPONSE = (
    "Some preamble text\n"
    "<!-- leadsync:wf6 -->\n"
    "Implementation scan for KAN-35:\n"
    "IMPLEMENTATION_SUMMARY: Added user auth middleware and JWT validation\n"
    "FILES_CHANGED: src/auth.py, src/middleware.py, tests/test_auth.py\n"
)


def test_extract_wf6_valid_marker_with_summary_and_files():
    result = extract_wf6_implementation(WF6_RESPONSE)
    assert "Added user auth middleware and JWT validation" in result
    assert "Files: src/auth.py" in result


def test_extract_wf6_no_marker_returns_empty():
    result = extract_wf6_implementation("Just a normal Jira response with no marker")
    assert result == ""


def test_extract_wf6_fallback_when_no_implementation_summary():
    text = (
        "<!-- leadsync:wf6 -->\n"
        "Implementation scan for KAN-40:\n"
        "Refactored database layer\n"
        "Updated migration scripts\n"
    )
    result = extract_wf6_implementation(text)
    assert "Refactored database layer" in result
    assert "Updated migration scripts" in result


def test_extract_wf6_truncation_at_max_chars():
    text = (
        "<!-- leadsync:wf6 -->\n"
        "IMPLEMENTATION_SUMMARY: " + "A" * 400 + "\n"
    )
    result = extract_wf6_implementation(text, max_chars=50)
    assert len(result) == 50
    assert result.endswith("...")


def test_extract_wf6_files_changed_none_omitted():
    text = (
        "<!-- leadsync:wf6 -->\n"
        "IMPLEMENTATION_SUMMARY: Fixed login bug\n"
        "FILES_CHANGED: none\n"
    )
    result = extract_wf6_implementation(text)
    assert result == "Fixed login bug"
    assert "Files:" not in result


# -- _enrich_tickets_with_wf6 tests -------------------------------------------


def _make_ticket(key: str) -> HistoryTicket:
    return HistoryTicket(
        key=key,
        summary="Test summary",
        description_excerpt="Some description",
        status="Done",
        resolution_date="2026-02-27",
    )


def test_enrich_happy_path_populates_implementation_details():
    from src.common.jira_history_core import _enrich_tickets_with_wf6

    get_tool = MagicMock()
    get_tool.name = "JIRA_GET_ISSUE"
    get_tool.run.return_value = WF6_RESPONSE

    tickets = [_make_ticket("KAN-35")]
    _enrich_tickets_with_wf6([get_tool], tickets)

    assert "Added user auth middleware" in tickets[0].implementation_details


def test_enrich_no_get_issue_tool_leaves_tickets_unchanged():
    from src.common.jira_history_core import _enrich_tickets_with_wf6

    tickets = [_make_ticket("KAN-35")]
    _enrich_tickets_with_wf6([], tickets)

    assert tickets[0].implementation_details == ""


def test_enrich_exception_leaves_ticket_unchanged():
    from src.common.jira_history_core import _enrich_tickets_with_wf6

    get_tool = MagicMock()
    get_tool.name = "JIRA_GET_ISSUE"
    get_tool.run.side_effect = RuntimeError("API error")

    tickets = [_make_ticket("KAN-35")]
    _enrich_tickets_with_wf6([get_tool], tickets)

    assert tickets[0].implementation_details == ""


def test_enrich_multiple_tickets_only_wf6_ones_enriched():
    from src.common.jira_history_core import _enrich_tickets_with_wf6

    get_tool = MagicMock()
    get_tool.name = "JIRA_GET_ISSUE"
    get_tool.run.side_effect = [
        WF6_RESPONSE,
        "Plain response without marker",
    ]

    tickets = [_make_ticket("KAN-35"), _make_ticket("KAN-36")]
    _enrich_tickets_with_wf6([get_tool], tickets)

    assert tickets[0].implementation_details != ""
    assert tickets[1].implementation_details == ""


# -- build_same_label_progress_context with WF6 details -----------------------


def test_progress_context_prefers_wf6_details_over_description():
    from src.jira_history import build_same_label_progress_context

    search_tool = MagicMock()
    search_tool.name = "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST"
    search_tool.run.return_value = {
        "issues": [
            {
                "key": "KAN-35",
                "fields": {
                    "summary": "Add auth middleware",
                    "description": "Old description text",
                    "status": {"name": "Done"},
                    "resolutiondate": "2026-02-27T12:00:00.000+0000",
                },
            }
        ]
    }

    get_tool = MagicMock()
    get_tool.name = "JIRA_GET_ISSUE"
    get_tool.run.return_value = WF6_RESPONSE

    context = build_same_label_progress_context(
        tools=[search_tool, get_tool],
        project_key="KAN",
        label="backend",
        exclude_issue_key="KAN-40",
    )

    assert "Added user auth middleware and JWT validation" in context
    assert "Old description text" not in context
