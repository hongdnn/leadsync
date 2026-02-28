"""Read/query helpers for building Slack memory context prompts."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from src.memory.schema import init_memory_db

logger = logging.getLogger(__name__)


def query_slack_memory_context(
    db_path: str,
    ticket_key: str,
    project_key: str,
    label: str,
    component: str | None,
    repo_key: str | None = None,
    team_key: str | None = None,
    digest_days: int = 3,
    similar_limit: int = 5,
) -> str:
    """
    Build compact memory context block for Workflow 3 prompts.

    Returns:
        Plain text context containing ticket memory, digest signals, and similar Q&A.
    """
    init_memory_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        ticket_rows = conn.execute(
            """
            SELECT ticket_key, created_at, summary, decision
            FROM memory_items
            WHERE ticket_key = ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (ticket_key,),
        ).fetchall()
        digest_cutoff = (datetime.now(timezone.utc) - timedelta(days=digest_days)).isoformat()
        digest_sql = [
            "SELECT created_at, summary, decision FROM memory_items",
            "WHERE item_type = 'daily_digest_area' AND created_at >= ?",
        ]
        digest_args: list[Any] = [digest_cutoff]
        if project_key:
            digest_sql.append("AND project_key = ?")
            digest_args.append(project_key)
        if repo_key:
            digest_sql.append("AND repo_key = ?")
            digest_args.append(repo_key)
        if team_key:
            digest_sql.append("AND team_key = ?")
            digest_args.append(team_key)
        digest_sql.append("ORDER BY created_at DESC LIMIT 10")
        digest_rows = conn.execute(" ".join(digest_sql), tuple(digest_args)).fetchall()
        similar_rows: list[sqlite3.Row] = []
        if label:
            similar_sql = [
                "SELECT ticket_key, summary, context_json, created_at FROM memory_items",
                "WHERE item_type = 'slack_qa' AND label = ?",
            ]
            similar_args: list[Any] = [label]
            if component:
                similar_sql.append("AND component = ?")
                similar_args.append(component)
            similar_sql.append("AND COALESCE(ticket_key, '') != ?")
            similar_args.append(ticket_key)
            similar_sql.append("ORDER BY created_at DESC LIMIT ?")
            similar_args.append(similar_limit)
            similar_rows = conn.execute(" ".join(similar_sql), tuple(similar_args)).fetchall()
    lines = ["Memory Context", "Ticket Memory:"]
    if ticket_rows:
        for row in ticket_rows:
            decision = row["decision"] or "No decision captured."
            lines.append(f"- {row['created_at']} | {row['summary']} | Decision: {decision}")
    else:
        lines.append("- None.")
    lines.append("Recent Digest Signals:")
    if digest_rows:
        for row in digest_rows:
            decision = row["decision"] or "No follow-up noted."
            lines.append(f"- {row['created_at']} | {row['summary']} | Follow-up: {decision}")
    else:
        lines.append("- None.")
    lines.append("Similar Q&A:")
    if similar_rows:
        for row in similar_rows:
            question = ""
            try:
                question = json.loads(row["context_json"] or "{}").get("question", "")
            except Exception:
                logger.exception("Failed to parse stored memory context_json.")
            suffix = f" | Q: {question}" if question else ""
            lines.append(f"- {row['ticket_key']} | {row['summary']}{suffix}")
    else:
        lines.append("- None.")
    return "\n".join(lines)
