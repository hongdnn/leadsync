"""Workflow 3 context-loading helpers (Jira history, preferences, memory)."""

import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class Workflow3Context:
    """Resolved context required to build Workflow 3 tasks."""

    jira_tools: list[Any]
    preference_category: str
    team_preferences: str
    same_label_history: str
    memory_context: str
    project_key: str
    primary_label: str
    primary_component: str


def resolve_workflow3_context(
    *,
    ticket_key: str,
    jira_tools: list[Any],
    docs_tools: list[Any],
    resolve_preference_category: Callable[[list[str], list[str]], str],
    load_preferences_for_category: Callable[[str, list[Any]], str],
    load_issue_project_label_component: Callable[[list[Any], str], tuple[str, str, str]],
    build_same_label_progress_context: Callable[..., str],
    memory_enabled: Callable[[], bool],
    query_slack_memory_context: Callable[..., str],
    build_memory_db_path: Callable[[], str],
) -> Workflow3Context:
    """Resolve ticket metadata, preference text, same-label history, and memory context."""
    project_key, primary_label, primary_component = load_issue_project_label_component(
        tools=jira_tools, issue_key=ticket_key
    )
    preference_category = resolve_preference_category(
        labels=[primary_label] if primary_label else [],
        component_names=[primary_component] if primary_component else [],
    )
    team_preferences = load_preferences_for_category(preference_category, docs_tools)
    same_label_history = build_same_label_progress_context(
        tools=jira_tools,
        project_key=project_key,
        label=primary_label,
        exclude_issue_key=ticket_key,
        limit=10,
    )
    memory_context = "Memory context unavailable for this run."
    if memory_enabled():
        try:
            memory_context = query_slack_memory_context(
                db_path=build_memory_db_path(),
                ticket_key=ticket_key,
                project_key=project_key,
                label=primary_label,
                component=primary_component or None,
            )
        except Exception:
            logger.exception("Workflow 3 memory query failed for ticket '%s'.", ticket_key)
    return Workflow3Context(
        jira_tools=jira_tools,
        preference_category=preference_category,
        team_preferences=team_preferences,
        same_label_history=same_label_history,
        memory_context=memory_context,
        project_key=project_key,
        primary_label=primary_label,
        primary_component=primary_component,
    )
