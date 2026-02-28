"""
Workflow 6 runner implementation (Done Ticket Implementation Scan).
Exports: run_workflow6
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable

from src.common.model_retry import kickoff_with_model_fallback
from src.common.task_output import extract_task_output
from src.shared import CrewRunResult, _required_env
from src.workflow1.context import parse_issue_context
from src.workflow6.crew_build import build_done_scan_crew
from src.workflow6.ops import post_done_scan_comment

logger = logging.getLogger(__name__)


@dataclass
class Workflow6Runtime:
    """Runtime dependencies injected by top-level wrapper for test compatibility."""

    Agent: Any
    Task: Any
    Crew: Any
    Process: Any
    memory_enabled: Callable[[], bool]
    build_memory_db_path: Callable[[], str]
    record_event: Callable[..., None]


def run_workflow6(
    *,
    payload: dict[str, Any],
    model: str,
    github_tools: list[Any],
    jira_tools: list[Any],
    runtime: Workflow6Runtime,
) -> CrewRunResult:
    """Execute Workflow 6 end-to-end and return normalized crew run result.

    Args:
        payload: Jira webhook JSON body.
        model: LLM model name.
        github_tools: Composio GitHub tools for scanning.
        jira_tools: Composio Jira tools for comment posting.
        runtime: Runtime dependencies (CrewAI classes, memory helpers).
    Returns:
        CrewRunResult with summary and model used.
    """
    issue = parse_issue_context(payload)
    repo_owner = _required_env("LEADSYNC_GITHUB_REPO_OWNER")
    repo_name = _required_env("LEADSYNC_GITHUB_REPO_NAME")

    _scan_task, summarize_task, agents, crew = build_done_scan_crew(
        runtime=runtime,
        model=model,
        github_tools=github_tools,
        issue_key=issue.issue_key,
        summary=issue.summary,
        description=issue.issue_description,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )

    result, used_model = kickoff_with_model_fallback(
        crew=crew,
        model=model,
        agents=agents,
        logger=logger,
        label="DoneScan",
    )

    summary_text = extract_task_output(summarize_task)
    if not summary_text:
        summary_text = str(result)

    comment_status = post_done_scan_comment(
        jira_tools=jira_tools,
        issue_key=issue.issue_key,
        summary_text=summary_text,
        ticket_summary=issue.summary,
    )
    logger.info(
        "WF6 done-scan for %s: comment=%s model=%s",
        issue.issue_key,
        comment_status,
        used_model,
    )

    try:
        if runtime.memory_enabled():
            db_path = runtime.build_memory_db_path()
            runtime.record_event(
                db_path=db_path,
                event_type="done_scan_completed",
                workflow="workflow6",
                ticket_key=issue.issue_key,
                project_key=issue.project_key or None,
                label=issue.primary_label or None,
                component=issue.primary_component or None,
                payload={
                    "summary_text": summary_text,
                    "comment_status": comment_status,
                },
            )
    except Exception:
        logger.exception(
            "WF6 memory persistence failed for ticket '%s'.", issue.issue_key
        )

    return CrewRunResult(raw=summary_text, model=used_model)
