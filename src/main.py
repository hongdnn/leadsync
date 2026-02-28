"""
src/main.py
FastAPI application — all endpoints for LeadSync.
Endpoints: GET /health, POST /webhooks/jira, POST /digest/trigger, POST /slack/commands, POST /slack/prefs
"""

from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qs
import logging
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from dotenv import load_dotenv

from src.digest_crew import run_digest_crew
from src.jira_link_crew import run_jira_link_crew
from src.leadsync_crew import run_leadsync_crew
from src.memory_store import init_memory_db, record_memory_item
from src.pr_review_crew import run_pr_review_crew
from src.shared import build_memory_db_path, memory_enabled
from src.slack_crew import parse_slack_text, run_slack_crew

logger = logging.getLogger(__name__)
load_dotenv()

def initialize_memory() -> None:
    """Initialize SQLite memory schema at app startup (best-effort)."""
    if not memory_enabled():
        logger.info("LeadSync memory disabled via LEADSYNC_MEMORY_ENABLED.")
        return
    try:
        init_memory_db(build_memory_db_path())
    except Exception:
        logger.exception("Failed to initialize LeadSync memory store.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """FastAPI lifespan hook for startup/shutdown side effects."""
    initialize_memory()
    yield


app = FastAPI(title="LeadSync", lifespan=lifespan)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}


@app.post("/webhooks/jira")
def jira_webhook(payload: dict[str, Any]) -> dict[str, str]:
    """
    Trigger Workflow 1: Ticket Enrichment.

    Args:
        payload: Jira webhook JSON body.
    Returns:
        Status, model, and raw crew result.
    Raises:
        HTTPException 400: Missing env vars.
        HTTPException 500: Crew failure.
    """
    try:
        result = run_leadsync_crew(payload=payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crew run failed: {exc}") from exc
    return {"status": "processed", "model": result.model, "result": result.raw}


@app.post("/webhooks/github")
def github_webhook(payload: dict[str, Any]) -> dict[str, str]:
    """
    Trigger Workflow 4 (PR auto-description) and Workflow 5 (Jira PR auto-link).
    WF5 runs non-blocking — its failure does not affect WF4's response.

    Args:
        payload: GitHub webhook JSON body.
    Returns:
        Status + workflow results for WF4 and WF5.
    Raises:
        HTTPException 400: Missing env vars or malformed payload.
        HTTPException 500: Workflow 4 failure.
    """
    try:
        result4 = run_pr_review_crew(payload=payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workflow 4 failed: {exc}") from exc

    wf5_raw = "skipped:wf5-error"
    try:
        result5 = run_jira_link_crew(payload=payload)
        wf5_raw = result5.raw
    except Exception:
        logger.exception("Workflow 5 failed (non-blocking).")

    return {
        "status": "processed",
        "model": result4.model,
        "result": result4.raw,
        "wf5_result": wf5_raw,
    }


@app.post("/digest/trigger")
async def digest_trigger(request: Request) -> dict[str, str]:
    """
    Trigger Workflow 2: End-of-Day Digest.

    Returns:
        Status, model, and raw crew result.
    Raises:
        HTTPException 400: Missing env vars.
        HTTPException 401: Missing/invalid scheduler token.
        HTTPException 500: Crew failure.
    """
    _verify_digest_trigger_token(request)
    payload = await _parse_optional_json_body(request)
    run_source = str(payload.get("run_source", "manual")).strip().lower() or "manual"
    if run_source not in {"manual", "scheduled"}:
        raise HTTPException(status_code=400, detail="run_source must be 'manual' or 'scheduled'.")
    bucket_start_utc = str(payload.get("bucket_start_utc", "")).strip() or None
    window_minutes = _coerce_window_minutes(payload.get("window_minutes"))
    repo_owner = str(payload.get("repo_owner", "")).strip() or None
    repo_name = str(payload.get("repo_name", "")).strip() or None
    try:
        kwargs: dict[str, Any] = {
            "window_minutes": window_minutes,
            "run_source": run_source,
            "bucket_start_utc": bucket_start_utc,
        }
        if repo_owner:
            kwargs["repo_owner"] = repo_owner
        if repo_name:
            kwargs["repo_name"] = repo_name
        result = run_digest_crew(
            **kwargs
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crew run failed: {exc}") from exc
    return {"status": "processed", "model": result.model, "result": result.raw}


@app.post("/slack/commands")
async def slack_command(
    request: Request, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """
    Trigger Workflow 3: Slack Q&A.

    Accepts Slack slash command form-encoded payloads and JSON (for curl testing).
    Slack sends: application/x-www-form-urlencoded with a 'text' field.
    JSON alternative: {"ticket_key": "LEADS-1", "question": "...", "thread_ts": "..."}

    Args:
        request: FastAPI Request for flexible content-type handling.
    Returns:
        Status, model, and raw crew result.
    Raises:
        HTTPException 400: Missing env vars or missing fields.
        HTTPException 500: Crew failure.
    """
    content_type = request.headers.get("content-type", "")

    ticket_key = ""
    question = ""
    thread_ts = None
    channel_id = None

    if "application/x-www-form-urlencoded" in content_type:
        raw_body = await request.body()
        form_data = parse_qs(raw_body.decode("utf-8"))
        if form_data.get("ssl_check", [""])[0].strip() == "1":
            return {"status": "ok"}
        text = form_data.get("text", [""])[0].strip()
        if not text.strip():
            raise HTTPException(status_code=400, detail="Slack 'text' field is empty.")
        ticket_key, question = parse_slack_text(text)
        thread_ts = form_data.get("thread_ts", [""])[0].strip() or None
        channel_id = form_data.get("channel_id", [""])[0].strip() or None
        if not ticket_key:
            raise HTTPException(status_code=400, detail="ticket_key is required.")
        background_tasks.add_task(
            _run_slack_crew_background,
            ticket_key=ticket_key,
            question=question,
            thread_ts=thread_ts,
            channel_id=channel_id,
        )
        return {
            "response_type": "ephemeral",
            "text": f"LeadSync is processing {ticket_key} and will reply shortly.",
        }
    else:
        payload: dict[str, Any] = await request.json()
        ticket_key = payload.get("ticket_key", "").strip()
        question = payload.get("question", "")
        text = payload.get("text", "").strip()
        if not ticket_key and text:
            ticket_key, question = parse_slack_text(text)
        thread_ts = (
            payload.get("thread_ts", "").strip()
            or payload.get("message_ts", "").strip()
            or None
        )
        channel_id = payload.get("channel_id", "").strip() or None

    if not ticket_key:
        raise HTTPException(status_code=400, detail="ticket_key is required.")

    try:
        result = run_slack_crew(
            ticket_key=ticket_key,
            question=question,
            thread_ts=thread_ts,
            channel_id=channel_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crew run failed: {exc}") from exc

    return {"status": "processed", "model": result.model, "result": result.raw}


@app.post("/slack/prefs")
async def slack_prefs(request: Request) -> dict[str, str]:
    """
    Store a general leader rule via Slack slash command.

    Accepts Slack application/x-www-form-urlencoded payload with a 'text'
    field containing the rule to persist.

    Args:
        request: FastAPI Request for content-type handling.
    Returns:
        Confirmation message or `{"status":"ok"}` for Slack ssl_check probes.
    Raises:
        HTTPException 400: When text field is empty or memory is disabled.
    """
    raw_body = await request.body()
    form_data = parse_qs(raw_body.decode("utf-8"))

    if form_data.get("ssl_check", [""])[0].strip() == "1":
        return {"status": "ok"}

    text = form_data.get("text", [""])[0].strip()
    if not text:
        raise HTTPException(status_code=400, detail="Rule text is required.")

    if not memory_enabled():
        raise HTTPException(status_code=400, detail="Memory is disabled.")

    db_path = build_memory_db_path()
    record_memory_item(
        db_path=db_path,
        workflow="slack_prefs",
        item_type="leader_rule",
        summary=text,
    )
    return {
        "response_type": "ephemeral",
        "text": f"Leader rule saved: {text}",
    }


def _run_slack_crew_background(
    ticket_key: str,
    question: str,
    thread_ts: str | None,
    channel_id: str | None,
) -> None:
    """Run Slack Q&A crew in the background and log failures."""
    try:
        run_slack_crew(
            ticket_key=ticket_key,
            question=question,
            thread_ts=thread_ts,
            channel_id=channel_id,
        )
    except Exception:
        logger.exception("Background slack crew run failed for %s.", ticket_key)


def _verify_digest_trigger_token(request: Request) -> None:
    """
    Validate optional digest trigger token for scheduled invocations.

    Args:
        request: Incoming FastAPI request.
    Raises:
        HTTPException 401: When configured token is missing or incorrect.
    """
    expected = os.getenv("LEADSYNC_TRIGGER_TOKEN", "").strip()
    if not expected:
        return
    provided = request.headers.get("X-LeadSync-Trigger-Token", "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Unauthorized digest trigger.")


async def _parse_optional_json_body(request: Request) -> dict[str, Any]:
    """
    Parse optional JSON body for endpoints that also allow an empty payload.

    Args:
        request: Incoming FastAPI request.
    Returns:
        Parsed JSON dict or empty dict when body is absent.
    Raises:
        HTTPException 400: If non-empty body cannot be parsed as JSON object.
    """
    body = await request.body()
    if not body:
        return {}
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    return payload


def _coerce_window_minutes(value: Any) -> int | None:
    """
    Convert optional window value to positive int.

    Args:
        value: Raw JSON value from request.
    Returns:
        Parsed positive integer, or None when not provided.
    Raises:
        HTTPException 400: When provided value is not a positive integer.
    """
    if value is None:
        return None
    try:
        minutes = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="window_minutes must be a positive integer.") from exc
    if minutes <= 0:
        raise HTTPException(status_code=400, detail="window_minutes must be a positive integer.")
    return minutes
