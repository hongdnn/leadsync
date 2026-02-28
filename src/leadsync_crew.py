"""
src/leadsync_crew.py
Workflow 1: Ticket Enrichment compatibility wrapper.
Exports: run_leadsync_crew(payload) -> CrewRunResult
"""

import logging
from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task

from src.config import Config
from src.common.task_output import extract_task_output as _extract_task_output
from src.common.text_extract import extract_text as _extract_text
from src.common.token_matching import normalize_tokens as _normalize_tokens
from src.common.tool_helpers import (
    find_tool_by_name as _find_tool_by_name,
    has_tool_prefix as _has_tool_prefix,
    tool_name_set as _tool_name_set,
)
from src.jira_history import build_same_label_progress_context, extract_primary_label
from src.memory_store import record_event, record_memory_item
from src.prefs import load_preferences_for_category, resolve_preference_category
from src.shared import CrewRunResult, build_memory_db_path, build_tools, memory_enabled
from src.tools.jira_tools import get_agent_tools
from src.workflow1.prompt_artifact import (
    REQUIRED_SECTIONS,
    attach_prompt_file as _attach_prompt_file_impl,
    has_required_sections as _has_required_sections,
    normalize_prompt_markdown as _normalize_prompt_markdown,
    safe_issue_key_for_filename as _safe_issue_key_for_filename,
    write_prompt_file as _write_prompt_file_impl,
)
from src.workflow1.rules import select_ruleset_file as _select_ruleset_file
from src.workflow1.runner import Workflow1Runtime, run_workflow1

logger = logging.getLogger(__name__)
ARTIFACT_DIR = Path("artifacts") / "workflow1"


def _merge_tools(*tool_lists: list[Any]) -> list[Any]:
    """Merge tool lists while preserving first-seen order by tool name."""
    merged: list[Any] = []
    seen: set[str] = set()
    for tool_list in tool_lists:
        for tool in tool_list:
            name = getattr(tool, "name", "")
            dedupe_key = str(name).upper() or str(id(tool))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            merged.append(tool)
    return merged


def _required_sections() -> list[str]:
    """Return required Workflow 1 markdown headings."""
    return list(REQUIRED_SECTIONS)


def _write_prompt_file(issue_key: str, markdown: str) -> Path:
    """Persist prompt markdown artifact to disk using wrapper-configured artifact dir."""
    return _write_prompt_file_impl(ARTIFACT_DIR, issue_key, markdown)


def _attach_prompt_file(tools: list[Any], issue_key: str, file_path: Path) -> Any:
    """Attach local prompt file to Jira issue via Composio attachment tool."""
    return _attach_prompt_file_impl(tools, issue_key, file_path)


def run_leadsync_crew(payload: dict[str, Any]) -> CrewRunResult:
    """
    Run the Workflow 1 Ticket Enrichment crew.

    Args:
        payload: Jira webhook JSON body.
    Returns:
        CrewRunResult containing raw crew output and effective model name.
    """
    Config.require_gemini_api_key()
    model = Config.get_gemini_model()
    jira_tools = get_agent_tools()
    github_tools = build_tools(user_id=Config.get_composio_user_id(), toolkits=["GITHUB"])
    tools = _merge_tools(jira_tools, github_tools)
    docs_tools = build_tools(user_id=Config.get_composio_user_id(), toolkits=["GOOGLEDOCS"])
    repo_owner = Config.require_env("LEADSYNC_GITHUB_REPO_OWNER")
    repo_name = Config.require_env("LEADSYNC_GITHUB_REPO_NAME")
    runtime = Workflow1Runtime(
        Agent=Agent,
        Task=Task,
        Crew=Crew,
        Process=Process,
        select_ruleset_file=_select_ruleset_file,
        resolve_preference_category=resolve_preference_category,
        load_preferences_for_category=load_preferences_for_category,
        build_same_label_progress_context=build_same_label_progress_context,
        write_prompt_file=_write_prompt_file,
        attach_prompt_file=_attach_prompt_file,
        memory_enabled=memory_enabled,
        build_memory_db_path=build_memory_db_path,
        record_event=record_event,
        record_memory_item=record_memory_item,
    )
    return run_workflow1(
        payload=payload,
        model=model,
        tools=tools,
        docs_tools=docs_tools,
        runtime=runtime,
        logger=logger,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )
