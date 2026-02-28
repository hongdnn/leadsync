"""Workflow 2 runner implementation (End-of-Day Digest)."""

from dataclasses import dataclass
import logging
from typing import Any, Callable

from src.common.model_retry import kickoff_with_model_fallback
from src.shared import CrewRunResult
from src.workflow2.ops import maybe_acquire_digest_lock, persist_digest_memory


@dataclass
class Workflow2Runtime:
    """Runtime dependencies injected by top-level wrapper for test compatibility."""

    Agent: Any
    Task: Any
    Crew: Any
    Process: Any
    memory_enabled: Callable[[], bool]
    build_memory_db_path: Callable[[], str]
    record_event: Callable[..., None]
    record_memory_item: Callable[..., None]
    acquire_idempotency_lock: Callable[..., bool]


def run_workflow2(
    *,
    model: str,
    slack_channel_id: str,
    github_tools: list[Any],
    slack_tools: list[Any],
    runtime: Workflow2Runtime,
    logger: logging.Logger,
    window_minutes: int,
    run_source: str,
    bucket_start_utc: str | None,
    idempotency_enabled: bool,
) -> CrewRunResult:
    """Execute Workflow 2 end-to-end and return crew result."""
    maybe_skip = maybe_acquire_digest_lock(
        runtime=runtime,
        logger=logger,
        window_minutes=window_minutes,
        run_source=run_source,
        bucket_start_utc=bucket_start_utc,
        idempotency_enabled=idempotency_enabled,
        model=model,
    )
    if maybe_skip is not None:
        return maybe_skip

    digest_label = "Daily" if window_minutes >= 1440 else "Hourly"
    scanner = runtime.Agent(
        role="GitHub Scanner",
        goal=(
            "Collect meaningful main-branch commit activity "
            f"from the last {window_minutes} minutes."
        ),
        backstory="You gather commit signals only and avoid speculation.",
        verbose=True,
        tools=github_tools,
        llm=model,
    )
    writer = runtime.Agent(
        role="Digest Writer",
        goal="Group the scanned work by area and produce a concise team digest.",
        backstory="You write clear summaries for engineers and avoid generic filler.",
        verbose=True,
        llm=model,
    )
    poster = runtime.Agent(
        role="Slack Poster",
        goal=f"Post the digest to Slack channel {slack_channel_id}.",
        backstory="You publish the final digest message exactly once with clear formatting.",
        verbose=True,
        tools=slack_tools,
        llm=model,
    )
    scan_task = runtime.Task(
        description=(
            "Use GITHUB tools to scan main-branch changes "
            f"from the last {window_minutes} minutes.\n"
            "- Include author, commit summary, impacted area, and risk flags.\n"
            "- Exclude noise-only commits when possible."
        ),
        expected_output="Structured list of meaningful commits grouped by area.",
        agent=scanner,
    )
    write_task = runtime.Task(
        description=(
            f"Draft a concise {digest_label.lower()} digest from scanned commits.\n"
            "- Group by subsystem.\n"
            "- Mention key risks and follow-ups.\n"
            "- Keep under 12 lines.\n"
            "- Output lines in this exact format:\n"
            "  AREA: <name> | SUMMARY: <text> | RISKS: <text>"
        ),
        expected_output="A polished plain-text daily digest message.",
        agent=writer,
        context=[scan_task],
    )
    post_task = runtime.Task(
        description=(
            f"Post the digest to Slack channel {slack_channel_id} using SLACK tools.\n"
            f"- Prefix with '[LeadSync {digest_label} Digest]'.\n"
            "- Preserve line breaks for readability."
        ),
        expected_output="Confirmation that the digest was posted to Slack.",
        agent=poster,
        context=[write_task],
    )
    crew = runtime.Crew(
        agents=[scanner, writer, poster],
        tasks=[scan_task, write_task, post_task],
        process=runtime.Process.sequential,
        verbose=True,
    )
    result, used_model = kickoff_with_model_fallback(
        crew=crew,
        model=model,
        agents=[scanner, writer, poster],
        logger=logger,
        label="Digest",
    )
    persist_digest_memory(
        runtime=runtime,
        logger=logger,
        scan_task=scan_task,
        write_task=write_task,
        window_minutes=window_minutes,
        run_source=run_source,
        bucket_start_utc=bucket_start_utc,
    )
    return CrewRunResult(raw=str(result), model=used_model)
