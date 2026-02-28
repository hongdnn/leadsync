"""Write helpers for LeadSync SQLite memory tables."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from src.memory.schema import init_memory_db


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_text(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=True, default=str)


def record_event(
    db_path: str,
    event_type: str,
    workflow: str,
    payload: dict[str, Any],
    ticket_key: str | None = None,
    project_key: str | None = None,
    label: str | None = None,
    component: str | None = None,
) -> None:
    """Insert one event row."""
    init_memory_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO events (
                event_type, workflow, ticket_key, project_key, label, component, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                workflow,
                ticket_key,
                project_key,
                label,
                component,
                _json_text(payload),
                _utc_now_iso(),
            ),
        )


def record_memory_item(
    db_path: str,
    workflow: str,
    item_type: str,
    summary: str,
    ticket_key: str | None = None,
    project_key: str | None = None,
    label: str | None = None,
    component: str | None = None,
    repo_key: str | None = None,
    team_key: str | None = None,
    decision: str | None = None,
    rules_applied: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Insert one curated memory row."""
    init_memory_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO memory_items (
                workflow, item_type, ticket_key, project_key, label, component,
                repo_key, team_key, summary, decision, rules_applied, context_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow,
                item_type,
                ticket_key,
                project_key,
                label,
                component,
                repo_key,
                team_key,
                summary,
                decision,
                rules_applied,
                _json_text(context),
                _utc_now_iso(),
            ),
        )


def acquire_idempotency_lock(db_path: str, workflow: str, lock_key: str) -> bool:
    """
    Attempt to acquire a unique workflow lock key.

    Args:
        db_path: SQLite path.
        workflow: Workflow identifier.
        lock_key: Deterministic lock value for one logical run.
    Returns:
        True when lock row inserted; False when already present.
    """
    init_memory_db(db_path)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO idempotency_locks (workflow, lock_key, created_at)
                VALUES (?, ?, ?)
                """,
                (workflow, lock_key, _utc_now_iso()),
            )
        return True
    except sqlite3.IntegrityError:
        return False
