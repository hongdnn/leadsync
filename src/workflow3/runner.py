"""Workflow 3 runner implementation (Slack Q&A)."""

from dataclasses import dataclass
import logging
from typing import Any, Callable

from src.common.model_retry import kickoff_with_model_fallback
from src.common.task_output import extract_task_output
from src.shared import CrewRunResult
from src.workflow3.context import resolve_workflow3_context
from src.workflow3.crew_build import build_workflow3_crew


@dataclass
class Workflow3Runtime:
    """Runtime dependencies injected by top-level wrapper for test compatibility."""

    Agent: Any
    Task: Any
    Crew: Any
    Process: Any
    load_issue_project_label_component: Callable[[list[Any], str], tuple[str, str, str]]
    resolve_preference_category: Callable[[list[str], list[str]], str]
    load_preferences_for_category: Callable[[str, list[Any]], str]
    build_same_label_progress_context: Callable[..., str]
    memory_enabled: Callable[[], bool]
    build_memory_db_path: Callable[[], str]
    query_slack_memory_context: Callable[..., str]
    record_event: Callable[..., None]
    record_memory_item: Callable[..., None]


def run_workflow3(
    *,
    ticket_key: str,
    question: str,
    model: str,
    thread_ts: str | None,
    slack_channel_id: str,
    jira_tools: list[Any],
    docs_tools: list[Any],
    slack_tools: list[Any],
    runtime: Workflow3Runtime,
    logger: logging.Logger,
) -> CrewRunResult:
    """Execute Workflow 3 end-to-end and return normalized crew run result."""
    context = resolve_workflow3_context(
        ticket_key=ticket_key,
        jira_tools=jira_tools,
        docs_tools=docs_tools,
        resolve_preference_category=runtime.resolve_preference_category,
        load_preferences_for_category=runtime.load_preferences_for_category,
        load_issue_project_label_component=runtime.load_issue_project_label_component,
        build_same_label_progress_context=runtime.build_same_label_progress_context,
        memory_enabled=runtime.memory_enabled,
        query_slack_memory_context=runtime.query_slack_memory_context,
        build_memory_db_path=runtime.build_memory_db_path,
    )
    retrieve_task, reason_task, _respond_task, agents, crew = build_workflow3_crew(
        runtime=runtime,
        model=model,
        ticket_key=ticket_key,
        question=question,
        thread_ts=thread_ts,
        slack_channel_id=slack_channel_id,
        jira_tools=context.jira_tools,
        slack_tools=slack_tools,
        same_label_history=context.same_label_history,
        memory_context=context.memory_context,
        primary_label=context.primary_label,
        preference_category=context.preference_category,
        team_preferences=context.team_preferences,
    )
    result, used_model = kickoff_with_model_fallback(
        crew=crew,
        model=model,
        agents=agents,
        logger=logger,
        label="Slack",
    )
    try:
        if runtime.memory_enabled():
            answer_text = extract_task_output(reason_task)
            db_path = runtime.build_memory_db_path()
            runtime.record_event(
                db_path=db_path,
                event_type="slack_question_answered",
                workflow="workflow3",
                ticket_key=ticket_key,
                project_key=context.project_key or None,
                label=context.primary_label or None,
                component=context.primary_component or None,
                payload={
                    "question": question,
                    "answer": answer_text,
                    "thread_ts": thread_ts,
                    "channel_id": slack_channel_id,
                },
            )
            runtime.record_memory_item(
                db_path=db_path,
                workflow="workflow3",
                item_type="slack_qa",
                ticket_key=ticket_key,
                project_key=context.project_key or None,
                label=context.primary_label or None,
                component=context.primary_component or None,
                summary=answer_text or "No answer captured.",
                rules_applied=f"googledocs-{context.preference_category} + same-label-history",
                context={"question": question, "thread_ts": thread_ts, "channel_id": slack_channel_id},
            )
    except Exception:
        logger.exception("Workflow 3 memory persistence failed for ticket '%s'.", ticket_key)
    return CrewRunResult(raw=str(result), model=used_model)
