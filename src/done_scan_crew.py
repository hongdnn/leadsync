"""
src/done_scan_crew.py
Workflow 6: Done Ticket Implementation Scan public wrapper.
Exports: run_done_scan_crew(payload) -> CrewRunResult
"""

from typing import Any

from crewai import Agent, Crew, Process, Task

from src.memory_store import record_event
from src.shared import (
    CrewRunResult,
    build_llm,
    build_memory_db_path,
    build_tools,
    composio_user_id,
    memory_enabled,
)
from src.workflow6.runner import Workflow6Runtime, run_workflow6


def run_done_scan_crew(payload: dict[str, Any]) -> CrewRunResult:
    """Run the Workflow 6 Done Ticket Implementation Scan crew.

    Args:
        payload: Jira webhook JSON body.
    Returns:
        CrewRunResult containing raw crew output and effective model name.
    """
    user_id = composio_user_id()
    model = build_llm()
    github_tools = build_tools(user_id=user_id, toolkits=["GITHUB"])
    jira_tools = build_tools(
        user_id=user_id, tools=["JIRA_GET_ISSUE", "JIRA_ADD_COMMENT"]
    )
    runtime = Workflow6Runtime(
        Agent=Agent,
        Task=Task,
        Crew=Crew,
        Process=Process,
        memory_enabled=memory_enabled,
        build_memory_db_path=build_memory_db_path,
        record_event=record_event,
    )
    return run_workflow6(
        payload=payload,
        model=model,
        github_tools=github_tools,
        jira_tools=jira_tools,
        runtime=runtime,
    )
