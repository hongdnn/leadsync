"""Workflow 1 runner implementation (Ticket Enrichment)."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Callable

from src.common.model_retry import kickoff_with_model_fallback
from src.common.task_output import extract_task_output
from src.common.tool_helpers import has_tool_prefix, tool_name_set
from src.shared import CrewRunResult
from src.workflow1.context import IssueContext, parse_issue_context
from src.workflow1.crew_build import build_workflow1_crew
from src.workflow1.prompt_artifact import normalize_prompt_markdown
from src.workflow1.rules import load_ruleset_content


@dataclass
class Workflow1Runtime:
    """Runtime dependencies to preserve test patch points in wrapper module."""

    Agent: Any
    Task: Any
    Crew: Any
    Process: Any
    select_ruleset_file: Callable[[list[str], list[str]], str]
    resolve_preference_category: Callable[[list[str], list[str]], str]
    load_preferences_for_category: Callable[[str, list[Any]], str]
    build_same_label_progress_context: Callable[..., str]
    write_prompt_file: Callable[[str, str], Path]
    attach_prompt_file: Callable[[list[Any], str, Path], Any]
    memory_enabled: Callable[[], bool]
    build_memory_db_path: Callable[[], str]
    record_event: Callable[..., None]
    record_memory_item: Callable[..., None]


def _common_context(issue: IssueContext) -> str:
    return (
        f"Issue key: {issue.issue_key}\n"
        f"Summary: {issue.summary}\n"
        f"Description: {issue.issue_description or 'No description provided.'}\n"
        f"Labels: {issue.labels}\n"
        f"Primary label: {issue.primary_label or 'N/A'}\n"
        f"Assignee: {issue.assignee}\n"
        f"Project: {issue.project_key}\n"
        f"Components: {issue.component_names}\n"
    )


def run_workflow1(
    *,
    payload: dict[str, Any],
    model: str,
    tools: list[Any],
    docs_tools: list[Any],
    runtime: Workflow1Runtime,
    logger: logging.Logger,
) -> CrewRunResult:
    """Execute Workflow 1 end-to-end and return normalized crew run result."""
    issue = parse_issue_context(payload)
    tool_names = tool_name_set(tools)
    has_jira_get_issue = "JIRA_GET_ISSUE" in tool_names
    has_jira_edit_issue = "JIRA_EDIT_ISSUE" in tool_names
    has_jira_add_comment = "JIRA_ADD_COMMENT" in tool_names
    has_jira_add_attachment = "JIRA_ADD_ATTACHMENT" in tool_names
    has_github_tools = has_tool_prefix(tool_names, "GITHUB_")
    ruleset_file = runtime.select_ruleset_file(issue.labels, issue.component_names)
    ruleset_content = load_ruleset_content(ruleset_file)
    preference_category = runtime.resolve_preference_category(issue.labels, issue.component_names)
    team_preferences = runtime.load_preferences_for_category(preference_category, docs_tools)
    same_label_history = runtime.build_same_label_progress_context(
        tools=tools,
        project_key=issue.project_key,
        label=issue.primary_label,
        exclude_issue_key=issue.issue_key,
        limit=10,
    )
    context_text = _common_context(issue) + f"Same-label history context:\n{same_label_history}\n"
    gather_task, reason_task, _propagate_task, agents, crew = build_workflow1_crew(
        runtime=runtime,
        model=model,
        tools=tools,
        tool_names=tool_names,
        context_text=context_text,
        ruleset_file=ruleset_file,
        ruleset_content=ruleset_content,
        preference_category=preference_category,
        team_preferences=team_preferences,
        has_jira_get_issue=has_jira_get_issue,
        has_jira_edit_issue=has_jira_edit_issue,
        has_jira_add_comment=has_jira_add_comment,
        has_jira_add_attachment=has_jira_add_attachment,
        has_github_tools=has_github_tools,
    )
    result, used_model = kickoff_with_model_fallback(
        crew=crew,
        model=model,
        agents=agents,
        logger=logger,
        label="LeadSync",
    )
    gathered = extract_task_output(gather_task)
    reasoned = extract_task_output(reason_task)
    prompt_markdown = normalize_prompt_markdown(
        reasoner_text=reasoned,
        issue_key=issue.issue_key,
        summary=issue.summary,
        gathered_context=gathered,
        ruleset_content=ruleset_content,
    )
    prompt_path = runtime.write_prompt_file(issue.issue_key, prompt_markdown)
    runtime.attach_prompt_file(tools, issue.issue_key, prompt_path)
    try:
        if runtime.memory_enabled():
            db_path = runtime.build_memory_db_path()
            runtime.record_event(
                db_path=db_path,
                event_type="ticket_enrichment_run",
                workflow="workflow1",
                ticket_key=issue.issue_key,
                project_key=issue.project_key,
                label=issue.primary_label or None,
                component=issue.primary_component or None,
                payload={"ruleset_file": ruleset_file, "model": used_model, "prompt_file": str(prompt_path)},
            )
            runtime.record_memory_item(
                db_path=db_path,
                workflow="workflow1",
                item_type="ticket_enrichment",
                ticket_key=issue.issue_key,
                project_key=issue.project_key,
                label=issue.primary_label or None,
                component=issue.primary_component or None,
                summary=(issue.summary or f"Technical guidance prepared for {issue.issue_key}").strip(),
                decision=(reasoned or "No explicit decision text captured.").strip(),
                rules_applied=ruleset_file,
                context={"same_label_history": same_label_history, "gathered_context": gathered},
            )
    except Exception:
        logger.exception("Workflow 1 memory persistence failed for issue '%s'.", issue.issue_key)
    return CrewRunResult(raw=str(result), model=used_model)
