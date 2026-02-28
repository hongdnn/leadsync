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
from src.workflow1.key_files import (
    filter_demo_key_files,
    format_key_files_markdown,
    parse_key_files,
    suggest_demo_key_files,
)
from src.workflow1.ops import persist_workflow1_memory, validate_github_requirements
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
    repo_owner: str,
    repo_name: str,
) -> CrewRunResult:
    """Execute Workflow 1 end-to-end and return normalized crew run result."""
    issue = parse_issue_context(payload)
    tool_names = tool_name_set(tools)
    has_jira_get_issue = "JIRA_GET_ISSUE" in tool_names
    has_jira_edit_issue = "JIRA_EDIT_ISSUE" in tool_names
    has_jira_add_comment = "JIRA_ADD_COMMENT" in tool_names
    has_jira_add_attachment = "JIRA_ADD_ATTACHMENT" in tool_names
    has_github_tools = has_tool_prefix(tool_names, "GITHUB_")
    validate_github_requirements(
        repo_owner=repo_owner,
        repo_name=repo_name,
        has_github_tools=has_github_tools,
    )
    ruleset_file = runtime.select_ruleset_file(issue.labels, issue.component_names)
    ruleset_content = load_ruleset_content(ruleset_file)
    preference_category = runtime.resolve_preference_category(issue.labels, issue.component_names)
    team_preferences = runtime.load_preferences_for_category(preference_category, docs_tools)
    same_label_history = runtime.build_same_label_progress_context(
        tools=tools,
        project_key=issue.project_key,
        label=issue.primary_label,
        exclude_issue_key=issue.issue_key,
        limit=5,
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
        repo_owner=repo_owner,
        repo_name=repo_name,
    )
    result, used_model = kickoff_with_model_fallback(
        crew=crew,
        model=model,
        agents=agents,
        logger=logger,
        label="LeadSync",
    )
    gathered = extract_task_output(gather_task)
    parsed_key_files = parse_key_files(gathered)
    key_files = filter_demo_key_files(parsed_key_files)
    if not key_files:
        issue_text = f"{issue.summary}\n{issue.issue_description or ''}\nLabels: {' '.join(issue.labels)}"
        key_files = suggest_demo_key_files(issue_text=issue_text, repo_root=Path.cwd())
    if not key_files:
        raise RuntimeError(
            "Workflow 1 found no demo-scoped key-file suggestions under /demo."
        )
    key_files_markdown = format_key_files_markdown(key_files)
    reasoned = extract_task_output(reason_task)
    prompt_markdown = normalize_prompt_markdown(
        reasoner_text=reasoned,
        issue_key=issue.issue_key,
        summary=issue.summary,
        gathered_context=gathered,
        key_files_markdown=key_files_markdown,
        ruleset_content=ruleset_content,
    )
    prompt_path = runtime.write_prompt_file(issue.issue_key, prompt_markdown)
    runtime.attach_prompt_file(tools, issue.issue_key, prompt_path)
    persist_workflow1_memory(
        runtime=runtime,
        logger=logger,
        issue=issue,
        ruleset_file=ruleset_file,
        used_model=used_model,
        prompt_path=prompt_path,
        reasoned=reasoned,
        same_label_history=same_label_history,
        gathered=gathered,
        key_files_markdown=key_files_markdown,
        repo_owner=repo_owner,
        repo_name=repo_name,
        key_file_count=len(key_files),
    )
    return CrewRunResult(raw=str(result), model=used_model)
