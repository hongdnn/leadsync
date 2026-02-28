"""Workflow 2 operational helpers (idempotency + memory persistence)."""

import logging
from typing import Any

from src.common.task_output import extract_task_output
from src.shared import CrewRunResult
from src.workflow2.parsing import parse_digest_blocks


def maybe_acquire_digest_lock(
    *,
    runtime: Any,
    logger: logging.Logger,
    window_minutes: int,
    run_source: str,
    bucket_start_utc: str | None,
    idempotency_enabled: bool,
    model: str,
) -> CrewRunResult | None:
    """Acquire digest idempotency lock or return a skip result when duplicated."""
    if not (idempotency_enabled and bucket_start_utc and runtime.memory_enabled()):
        return None
    lock_key = f"digest:{bucket_start_utc}:window={window_minutes}:source={run_source}"
    try:
        db_path = runtime.build_memory_db_path()
        acquired = runtime.acquire_idempotency_lock(
            db_path=db_path, workflow="workflow2", lock_key=lock_key
        )
        if not acquired:
            logger.info("Skipping duplicate digest bucket: %s", lock_key)
            return CrewRunResult(raw=f"skipped: duplicate bucket {bucket_start_utc}", model=model)
    except Exception:
        logger.exception("Workflow 2 idempotency lock failed; continuing run.")
    return None


def persist_digest_memory(
    *,
    runtime: Any,
    logger: logging.Logger,
    scan_task: Any,
    write_task: Any,
    window_minutes: int,
    run_source: str,
    bucket_start_utc: str | None,
) -> None:
    """Persist Workflow 2 event + digest area memory entries (best-effort)."""
    try:
        if runtime.memory_enabled():
            db_path = runtime.build_memory_db_path()
            scan_text = extract_task_output(scan_task)
            digest_text = extract_task_output(write_task)
            area_blocks = parse_digest_blocks(digest_text)
            runtime.record_event(
                db_path=db_path,
                event_type="github_commit_batch",
                workflow="workflow2",
                payload={
                    "scan_summary": scan_text,
                    "window_minutes": window_minutes,
                    "run_source": run_source,
                    "bucket_start_utc": bucket_start_utc,
                },
            )
            for block in area_blocks:
                runtime.record_memory_item(
                    db_path=db_path,
                    workflow="workflow2",
                    item_type="daily_digest_area",
                    summary=f"{block.area}: {block.summary}",
                    decision=block.decisions,
                    context={
                        "area": block.area,
                        "authors": block.authors,
                        "commits": block.commits,
                        "files": block.files,
                        "changes": block.changes,
                        "source": "digest_writer",
                    },
                )
            runtime.record_event(
                db_path=db_path,
                event_type="daily_digest_posted",
                workflow="workflow2",
                payload={
                    "digest_summary": digest_text,
                    "area_count": len(area_blocks),
                    "window_minutes": window_minutes,
                    "run_source": run_source,
                    "bucket_start_utc": bucket_start_utc,
                },
            )
    except Exception:
        logger.exception("Workflow 2 memory persistence failed.")
