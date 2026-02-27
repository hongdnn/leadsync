from typing import Any

from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

from src.leadsync_crew import run_leadsync_crew

load_dotenv()

app = FastAPI(title="LeadSync")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/jira")
def jira_webhook(payload: dict[str, Any]) -> dict[str, str]:
    try:
        result = run_leadsync_crew(payload=payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crew run failed: {exc}") from exc

    return {"status": "processed", "model": result.model, "result": result.raw}
