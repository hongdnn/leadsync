"""
src/main.py
FastAPI application — all endpoints for LeadSync.
Endpoints: GET /health, POST /webhooks/jira, POST /slack/commands
"""

from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from dotenv import load_dotenv

from src.leadsync_crew import run_leadsync_crew
from src.slack_crew import parse_slack_text, run_slack_crew

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


@app.post("/slack/commands")
async def slack_command(request: Request) -> dict[str, str]:
    """
    Trigger Workflow 3: Slack Q&A.

    Accepts Slack slash command form-encoded payloads and JSON (for curl testing).
    Slack sends: application/x-www-form-urlencoded with a 'text' field.
    JSON alternative: {"ticket_key": "LEADS-1", "question": "..."}

    Args:
        request: FastAPI Request for flexible content-type handling.
    Returns:
        Status, model, and raw crew result.
    Raises:
        HTTPException 400: Missing env vars or missing fields.
        HTTPException 500: Crew failure.
    """
    content_type = request.headers.get("content-type", "")

    if "application/x-www-form-urlencoded" in content_type:
        raw_body = await request.body()
        form_data = parse_qs(raw_body.decode("utf-8"))
        text = form_data.get("text", [""])[0].replace("+", " ")
        if not text.strip():
            raise HTTPException(status_code=400, detail="Slack 'text' field is empty.")
        ticket_key, question = parse_slack_text(text)
    else:
        payload: dict[str, Any] = await request.json()
        ticket_key = payload.get("ticket_key", "")
        question = payload.get("question", "")

    if not ticket_key:
        raise HTTPException(status_code=400, detail="ticket_key is required.")

    try:
        result = run_slack_crew(ticket_key=ticket_key, question=question)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crew run failed: {exc}") from exc

    return {"status": "processed", "model": result.model, "result": result.raw}
