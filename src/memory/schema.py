"""SQLite schema initialization for LeadSync hybrid memory."""

import sqlite3
from pathlib import Path


def prepare_db_path(db_path: str) -> Path:
    """Create parent directories for file-backed SQLite paths."""
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_memory_db(db_path: str) -> None:
    """
    Create memory tables and indexes when absent.

    Args:
        db_path: SQLite file path.
    Side effects:
        Creates SQLite file, schema, and indexes.
    """
    path = prepare_db_path(db_path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                workflow TEXT NOT NULL,
                ticket_key TEXT,
                project_key TEXT,
                label TEXT,
                component TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow TEXT NOT NULL,
                item_type TEXT NOT NULL,
                ticket_key TEXT,
                project_key TEXT,
                label TEXT,
                component TEXT,
                repo_key TEXT,
                team_key TEXT,
                summary TEXT NOT NULL,
                decision TEXT,
                rules_applied TEXT,
                context_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow TEXT NOT NULL,
                lock_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(workflow, lock_key)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_ticket_created ON events(ticket_key, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_workflow_created ON events(workflow, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_ticket ON memory_items(ticket_key, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_digest ON memory_items(item_type, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_similarity ON memory_items(label, component, item_type, created_at DESC)"
        )
