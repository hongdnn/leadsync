"""Workflow 2 runner implementation (End-of-Day Digest)."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
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
    repo_owner: str,
    repo_name: str,
    idempotency_enabled: bool,
) -> CrewRunResult:
    """Execute Workflow 2 end-to-end and return crew result."""
    since_dt = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

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
            "Collect all main-branch commit activity "
            f"from repository {repo_owner}/{repo_name} in the last {window_minutes} minutes."
        ),
        backstory="You gather every commit and report them all without filtering.",
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
            f"Use GITHUB tools only for repository {repo_owner}/{repo_name} "
            f"to list ALL commits on the main branch since {since_iso} (UTC).\n"
            f"Pass '{since_iso}' as the 'since' parameter when calling the GitHub API.\n"
            "- Include every commit — do not skip or filter any.\n"
            "- For each commit: author, commit message, and impacted area.\n"
            "- If no commits exist after that timestamp, return 'NO_COMMITS'."
        ),
        expected_output="Complete list of commits from the time window.",
        agent=scanner,
    )
    write_task = runtime.Task(
        description=(
            f"Draft a concise {digest_label.lower()} digest from all scanned commits.\n"
            "- Summarize key changes and new decisions made in the commits.\n"
            "- Group by subsystem or area.\n"
            "- Keep under 12 lines.\n"
            "- Output lines in this exact format:\n"
            "  AREA: <name> | SUMMARY: <text> | DECISIONS: <text>\n"
            "- If scanner output is 'NO_COMMITS', output exactly one line:\n"
            f"  AREA: general | SUMMARY: No commits in last {window_minutes} minutes. | DECISIONS: None."
        ),
        expected_output="A polished plain-text digest summarizing all changes and decisions.",
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
