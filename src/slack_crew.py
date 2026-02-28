"""
src/slack_crew.py
Workflow 3: Slack Q&A compatibility wrapper.
Exports: run_slack_crew(ticket_key, question, thread_ts, channel_id), parse_slack_text(text)
"""

import logging
import os

from crewai import Agent, Crew, Process, Task

from src.jira_history import build_same_label_progress_context, load_issue_project_label_component
from src.memory_store import query_slack_memory_context, record_event, record_memory_item
from src.prefs import load_preferences_for_category, resolve_preference_category
from src.shared import (
    CrewRunResult,
    _required_env,
    _required_gemini_api_key,
    build_llm,
    build_memory_db_path,
    build_tools,
    memory_enabled,
)
from src.tools.tool_registry import GOOGLEDOCS_PREFS_TOOLS, WF3_JIRA_TOOLS, WF3_SLACK_TOOLS
from src.workflow3.parsing import parse_slack_text
from src.workflow3.runner import Workflow3Runtime, run_workflow3

logger = logging.getLogger(__name__)


def run_slack_crew(
    ticket_key: str,
    question: str,
    thread_ts: str | None = None,
    channel_id: str | None = None,
) -> CrewRunResult:
    """Run Workflow 3 Slack Q&A crew and post response to Slack."""
    model = build_llm()
    _required_gemini_api_key()
    composio_user_id = os.getenv("COMPOSIO_USER_ID", "default")
    slack_channel_id = channel_id or _required_env("SLACK_CHANNEL_ID")
    runtime = Workflow3Runtime(
        Agent=Agent,
        Task=Task,
        Crew=Crew,
        Process=Process,
        load_issue_project_label_component=load_issue_project_label_component,
        resolve_preference_category=resolve_preference_category,
        load_preferences_for_category=load_preferences_for_category,
        build_same_label_progress_context=build_same_label_progress_context,
        memory_enabled=memory_enabled,
        build_memory_db_path=build_memory_db_path,
        query_slack_memory_context=query_slack_memory_context,
        record_event=record_event,
        record_memory_item=record_memory_item,
    )
    return run_workflow3(
        ticket_key=ticket_key,
        question=question,
        model=model,
        thread_ts=thread_ts,
        slack_channel_id=slack_channel_id,
        jira_tools=build_tools(user_id=composio_user_id, tools=WF3_JIRA_TOOLS),
        docs_tools=build_tools(user_id=composio_user_id, tools=GOOGLEDOCS_PREFS_TOOLS),
        slack_tools=build_tools(user_id=composio_user_id, tools=WF3_SLACK_TOOLS),
        runtime=runtime,
        logger=logger,
    )
