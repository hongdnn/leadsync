"""Workflow 1 operational helpers (validation and memory persistence)."""

import logging
from pathlib import Path
from typing import Any

from src.workflow1.context import IssueContext


def validate_github_requirements(
    *, repo_owner: str, repo_name: str, has_github_tools: bool
) -> None:
    """Validate required Workflow 1 GitHub repo target and tool availability."""
    if not repo_owner or not repo_name:
        raise RuntimeError(
            "Missing GitHub repository target. Set LEADSYNC_GITHUB_REPO_OWNER and "
            "LEADSYNC_GITHUB_REPO_NAME."
        )
    if not has_github_tools:
        raise RuntimeError(
            "Workflow 1 requires GitHub tools for key-file discovery. "
            "Connect GITHUB toolkit for COMPOSIO_USER_ID."
        )


def persist_workflow1_memory(
    *,
    runtime: Any,
    logger: logging.Logger,
    issue: IssueContext,
    preference_category: str,
    used_model: str,
    prompt_path: Path,
    reasoned: str,
    same_label_history: str,
    gathered: str,
    key_files_markdown: str,
    repo_owner: str,
    repo_name: str,
    key_file_count: int,
) -> None:
    """Persist Workflow 1 event/memory records with best-effort behavior."""
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
                payload={
                    "preference_category": preference_category,
                    "model": used_model,
                    "prompt_file": str(prompt_path),
                    "repo_owner": repo_owner,
                    "repo_name": repo_name,
                    "key_file_count": key_file_count,
                },
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
                rules_applied=preference_category,
                context={
                    "same_label_history": same_label_history,
                    "gathered_context": gathered,
                    "key_files_markdown": key_files_markdown,
                },
            )
    except Exception:
        logger.exception("Workflow 1 memory persistence failed for issue '%s'.", issue.issue_key)
