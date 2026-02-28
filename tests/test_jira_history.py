"""
tests/test_jira_history.py
Unit tests for src/jira_history.py shared same-label ticket history helpers.
"""

from unittest.mock import MagicMock


def test_extract_primary_label_returns_first_non_empty():
    from src.jira_history import extract_primary_label

    assert extract_primary_label(["", "backend", "frontend"]) == "backend"


def test_build_same_label_done_jql_contains_required_filters():
    from src.jira_history import build_same_label_done_jql

    jql = build_same_label_done_jql(
        project_key="LEADS",
        label="backend",
        exclude_issue_key="LEADS-99",
        limit=10,
    )
    assert 'project = "LEADS"' in jql
    assert 'labels = "backend"' in jql
    assert "statusCategory = Done" in jql
    assert 'key != "LEADS-99"' in jql
    assert "ORDER BY resolutiondate DESC" in jql


def test_build_same_label_progress_context_handles_missing_project_or_label():
    from src.jira_history import build_same_label_progress_context

    context = build_same_label_progress_context(
        tools=[],
        project_key="",
        label="",
        exclude_issue_key="LEADS-1",
    )
    assert "No comparable label history available" in context


def test_build_same_label_progress_context_handles_missing_search_tool():
    from src.jira_history import build_same_label_progress_context

    context = build_same_label_progress_context(
        tools=[],
        project_key="LEADS",
        label="backend",
        exclude_issue_key="LEADS-1",
    )
    assert "JIRA search tool unavailable" in context


def test_build_same_label_progress_context_formats_recent_tickets():
    from src.jira_history import build_same_label_progress_context

    search_tool = MagicMock()
    search_tool.name = "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST"
    search_tool.run.return_value = {
        "issues": [
            {
                "key": "LEADS-8",
                "fields": {
                    "summary": "Ship API throttling",
                    "description": "Added middleware, updated config defaults, and included retry docs.",
                    "status": {"name": "Done"},
                    "resolutiondate": "2026-02-27T12:00:00.000+0000",
                },
            }
        ]
    }
    context = build_same_label_progress_context(
        tools=[search_tool],
        project_key="LEADS",
        label="backend",
        exclude_issue_key="LEADS-9",
    )
    assert "Same-label completed tickets (latest 1)" in context
    assert "LEADS-8 [Done]" in context
    assert "Ship API throttling" in context
    assert "Added middleware" in context
    call_kwargs = search_tool.run.call_args.kwargs
    assert call_kwargs["max_results"] == 10
    assert "statusCategory = Done" in call_kwargs["jql"]
    assert "description" in call_kwargs["fields"]


def test_load_issue_project_and_label_from_get_issue_tool():
    from src.jira_history import load_issue_project_and_label

    issue_tool = MagicMock()
    issue_tool.name = "JIRA_GET_ISSUE"
    issue_tool.run.return_value = {
        "fields": {
            "project": {"key": "LEADS"},
            "labels": ["backend"],
        }
    }
    project_key, label = load_issue_project_and_label(
        tools=[issue_tool], issue_key="LEADS-1"
    )
    assert project_key == "LEADS"
    assert label == "backend"
