"""Workflow 2 runner implementation (End-of-Day Digest)."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Callable

from src.common.model_retry import kickoff_with_model_fallback
from src.shared import CrewRunResult
from src.stream import stream_enabled
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
            "Collect detailed commit activity from the main branch of "
            f"{repo_owner}/{repo_name} in the last {window_minutes} minutes, "
            "including file-level change details for every commit."
        ),
        backstory=(
            "You gather every commit with full details — author, message, "
            "and file-level changes — so the digest writer has rich data to work with."
        ),
        verbose=True,
        tools=github_tools,
        llm=model,
    )
    writer = runtime.Agent(
        role="Digest Writer",
        goal=(
            "Produce a technically detailed, diff-aware engineering digest grouped by area, "
            "including author names, commit counts, specific code-level changes, and key files."
        ),
        backstory=(
            "You are a senior engineer who reads diffs and patches to write precise digests. "
            "You always identify specific function names, parameter changes, logic modifications, "
            "and architectural decisions from the actual code changes — never generic filler."
        ),
        verbose=True,
        llm=model,
    )
    poster = runtime.Agent(
        role="Slack Poster",
        goal=f"Post the digest to Slack channel {slack_channel_id} with rich formatting.",
        backstory=(
            "You format and post engineering digests to Slack using mrkdwn. "
            "Each area gets a bold header, author attribution, and file references."
        ),
        verbose=True,
        tools=slack_tools,
        llm=model,
    )
    scan_task = runtime.Task(
        description=(
            f"Use GITHUB tools for repository {repo_owner}/{repo_name} "
            f"to list ALL commits on the main branch since {since_iso} (UTC).\n"
            f"Pass '{since_iso}' as the 'since' parameter when calling the GitHub API.\n\n"
            "STEP 1: List all commits since that timestamp. Include every commit — do not skip or filter any.\n"
            "STEP 2: For EACH commit, call GITHUB_GET_A_COMMIT with the commit SHA to get "
            "the full details including the list of files changed AND their patch/diff content.\n\n"
            "For each commit, report ALL of the following:\n"
            "- SHA: first 7 characters of the commit hash\n"
            "- AUTHOR: the committer's name or login\n"
            "- MESSAGE: the full commit message\n"
            "- FILES: for each changed file, include:\n"
            "  - file path and status (added/modified/removed)\n"
            "  - lines changed (+additions/-deletions)\n"
            "  - PATCH: the first 30 lines of the diff/patch content from the API response. "
            "This is critical — it shows exactly what code was added, removed, or modified. "
            "If the patch is longer than 30 lines, include the first 30 lines and note '...truncated'.\n\n"
            "The PATCH content is essential for the digest writer to produce specific, "
            "engineering-quality summaries. Do NOT omit patches.\n\n"
            "If no commits exist after that timestamp, return exactly 'NO_COMMITS'."
        ),
        expected_output=(
            "Detailed list of every commit with SHA, author, message, "
            "and file-level changes including file paths, status, lines changed, "
            "and patch/diff content (first 30 lines per file)."
        ),
        agent=scanner,
    )
    write_task = runtime.Task(
        description=(
            f"Draft a technically detailed {digest_label.lower()} engineering digest from the scanned commits.\n"
            "Group commits by subsystem or area (e.g., 'WF2 Digest', 'API', 'Auth', 'Testing').\n\n"
            "IMPORTANT: The scanner output includes PATCH/diff content for each file. You MUST read "
            "these patches carefully to identify specific function names, class changes, parameter "
            "modifications, and logic changes. Do NOT ignore the patch data.\n\n"
            "For EACH area, output a block in this EXACT format (one block per area):\n"
            "---\n"
            "AREA: <area name>\n"
            "AUTHORS: <comma-separated list of commit authors in this area>\n"
            "COMMITS: <number of commits in this area>\n"
            "FILES: <comma-separated list of key files changed, e.g. src/main.py (M), tests/test_api.py (A)>\n"
            "CHANGES:\n"
            "- <specific code-level change derived from the patch, e.g. 'Added retry_with_backoff(base_delay, max_retries) in ops.py'>\n"
            "- <another change, e.g. 'Refactored run_workflow2() to accept since_iso parameter'>\n"
            "- <another change, e.g. 'Removed deprecated legacy_parse() function from parsing.py'>\n"
            "SUMMARY: <2-3 sentences synthesizing the changes into a cohesive engineering narrative. "
            "Reference the specific functions and logic from CHANGES. Never write generic descriptions "
            "like 'made updates' or 'improved functionality'.>\n"
            "DECISIONS: <key technical decisions, trade-offs, or risks. If none, write 'None.'>\n"
            "---\n\n"
            "Rules:\n"
            "- Maximum 8 area blocks.\n"
            "- FILES uses (A)dded, (M)odified, (D)eleted status markers.\n"
            "- CHANGES must list 2-5 specific code-level changes per area, derived from patch content.\n"
            "  Each bullet must name a function, class, method, parameter, or specific logic change.\n"
            "  GOOD: 'Added _extract_block_fields(block: str) -> DigestArea in parsing.py'\n"
            "  GOOD: 'Changed run_scan() to pass since_iso instead of window_minutes'\n"
            "  BAD: 'Updated parsing logic' (too vague)\n"
            "  BAD: 'Made improvements to the runner' (no specifics)\n"
            "- Attribute work to specific authors — do not say 'the team'.\n"
            "- SUMMARY should reference the specific changes listed in CHANGES.\n"
            "- If scanner output is 'NO_COMMITS', output exactly:\n"
            "---\n"
            f"AREA: general\nAUTHORS: none\nCOMMITS: 0\nFILES: none\nCHANGES:\n- No changes\n"
            f"SUMMARY: No commits in the last {window_minutes} minutes.\n"
            "DECISIONS: None.\n"
            "---"
        ),
        expected_output=(
            "Multi-block digest with each area containing AREA, AUTHORS, COMMITS, "
            "FILES, CHANGES (specific code-level bullets), SUMMARY, and DECISIONS fields."
        ),
        agent=writer,
        context=[scan_task],
    )
    post_task = runtime.Task(
        description=(
            f"Post the digest to Slack channel {slack_channel_id} using SLACK tools.\n"
            "Format the message using Slack mrkdwn as follows:\n\n"
            f"Line 1: *[LeadSync {digest_label} Digest — {repo_owner}/{repo_name}]*\n"
            "Line 2: blank line\n"
            "Then for each area block from the digest:\n"
            "- *<AREA name>* (<COMMITS> commits by <AUTHORS>)\n"
            "- The SUMMARY text on the next line\n"
            "- The CHANGES bullets, each on its own line prefixed with '•' (bullet character)\n"
            "- `Key files:` followed by file names in inline code backticks\n"
            "- If DECISIONS is not 'None.', add: _Decisions: <text>_\n"
            "- Add a blank line between area blocks\n\n"
            "Keep the message readable and well-spaced. Do not add any commentary "
            "beyond what the digest writer produced."
        ),
        expected_output="Confirmation that the formatted digest was posted to Slack.",
        agent=poster,
        context=[write_task],
    )
    crew = runtime.Crew(
        agents=[scanner, writer, poster],
        tasks=[scan_task, write_task, post_task],
        process=runtime.Process.sequential,
        verbose=True,
        stream=stream_enabled(),
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
