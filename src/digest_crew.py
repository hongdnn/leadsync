"""
src/digest_crew.py
Workflow 2: End-of-Day Digest compatibility wrapper.
Exports: run_digest_crew() -> CrewRunResult
"""

import logging
import os

from crewai import Agent, Crew, Process, Task

from src.memory_store import acquire_idempotency_lock, record_event, record_memory_item
from src.shared import (
    CrewRunResult,
    _required_env,
    _required_gemini_api_key,
    build_digest_window_minutes,
    build_llm,
    build_memory_db_path,
    build_tools,
    digest_idempotency_enabled,
    memory_enabled,
)
from src.workflow2.parsing import parse_digest_areas as _parse_digest_areas
from src.workflow2.runner import Workflow2Runtime, run_workflow2

logger = logging.getLogger(__name__)


def run_digest_crew(
    *,
    window_minutes: int | None = None,
    run_source: str = "manual",
    bucket_start_utc: str | None = None,
) -> CrewRunResult:
    """
    Run Workflow 2 digest crew and return normalized result.

    Args:
        window_minutes: Optional override for commit lookback window.
        run_source: Source label for observability (manual/scheduled).
        bucket_start_utc: Optional UTC bucket marker for idempotency.
    Returns:
        CrewRunResult with raw result text and effective model.
    """
    model = build_llm()
    _required_gemini_api_key()
    composio_user_id = os.getenv("COMPOSIO_USER_ID", "default")
    slack_channel_id = _required_env("SLACK_CHANNEL_ID")
    effective_window = window_minutes or build_digest_window_minutes()
    runtime = Workflow2Runtime(
        Agent=Agent,
        Task=Task,
        Crew=Crew,
        Process=Process,
        memory_enabled=memory_enabled,
        build_memory_db_path=build_memory_db_path,
        record_event=record_event,
        record_memory_item=record_memory_item,
        acquire_idempotency_lock=acquire_idempotency_lock,
    )
    return run_workflow2(
        model=model,
        slack_channel_id=slack_channel_id,
        github_tools=build_tools(user_id=composio_user_id, toolkits=["GITHUB"]),
        slack_tools=build_tools(user_id=composio_user_id, toolkits=["SLACK"]),
        runtime=runtime,
        logger=logger,
        window_minutes=effective_window,
        run_source=run_source,
        bucket_start_utc=bucket_start_utc,
        idempotency_enabled=digest_idempotency_enabled(),
    )
