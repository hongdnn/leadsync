"""
src/main.py
FastAPI application — all endpoints for LeadSync.
Endpoints: GET /health, POST /webhooks/jira, POST /digest/trigger, POST /slack/commands, POST /slack/prefs
"""

from typing import Any
from urllib.parse import parse_qs
import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from dotenv import load_dotenv

from src.digest_crew import run_digest_crew
from src.leadsync_crew import run_leadsync_crew
from src.prefs import append_preference
from src.slack_crew import parse_slack_text, run_slack_crew

logger = logging.getLogger(__name__)
load_dotenv()

app = FastAPI(title="LeadSync")


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


@app.post("/digest/trigger")
def digest_trigger() -> dict[str, str]:
    """
    Trigger Workflow 2: End-of-Day Digest.

    Returns:
        Status, model, and raw crew result.
    Raises:
        HTTPException 400: Missing env vars.
        HTTPException 500: Crew failure.
    """
    try:
        result = run_digest_crew()
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
    Handle /leadsync-prefs Slack slash command to append team preferences.

    Accepts Slack application/x-www-form-urlencoded payload.
    Supported command: add <rule text>

    Args:
        request: FastAPI Request for content-type handling.
    Returns:
        Ephemeral Slack response confirming the preference was added.
    Raises:
        HTTPException 400: If text is empty or command is not 'add'.
    """
    raw_body = await request.body()
    form_data = parse_qs(raw_body.decode("utf-8"))

    if form_data.get("ssl_check", [""])[0].strip() == "1":
        return {"status": "ok"}

    text = form_data.get("text", [""])[0].strip()
    if not text:
        raise HTTPException(status_code=400, detail="Slack 'text' field is empty.")

    if not text.lower().startswith("add "):
        raise HTTPException(
            status_code=400,
            detail="Unknown command. Usage: /leadsync-prefs add <rule text>",
        )

    rule_text = text[4:].strip()
    if not rule_text:
        raise HTTPException(status_code=400, detail="Rule text cannot be empty.")

    try:
        append_preference(rule_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Preference write failed: {exc}") from exc
    return {
        "response_type": "ephemeral",
        "text": f"Preference added: {rule_text}",
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
