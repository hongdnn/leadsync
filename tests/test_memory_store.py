"""
tests/test_memory_store.py
Unit tests for src/memory_store.py.
"""

import sqlite3


def test_init_memory_db_creates_required_tables(tmp_path):
    from src.memory_store import init_memory_db

    db_path = tmp_path / "leadsync.db"
    init_memory_db(str(db_path))

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('events','memory_items')"
        ).fetchall()
    assert sorted(name for (name,) in rows) == ["events", "memory_items"]


def test_record_event_and_memory_item_persist(tmp_path):
    from src.memory_store import init_memory_db, record_event, record_memory_item

    db_path = tmp_path / "leadsync.db"
    init_memory_db(str(db_path))
    record_event(
        db_path=str(db_path),
        event_type="ticket_enrichment_run",
        workflow="workflow1",
        ticket_key="LEADS-1",
        project_key="LEADS",
        label="backend",
        component="auth",
        payload={"status": "ok"},
    )
    record_memory_item(
        db_path=str(db_path),
        workflow="workflow1",
        item_type="ticket_enrichment",
        ticket_key="LEADS-1",
        project_key="LEADS",
        label="backend",
        component="auth",
        summary="Enrichment created prompt artifact",
        decision="Touch auth service and add tests.",
        rules_applied="backend-ruleset.md",
        context={"same_label_count": 3},
    )

    with sqlite3.connect(db_path) as conn:
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        memory_count = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
    assert event_count == 1
    assert memory_count == 1


def test_query_slack_memory_context_filters_similar_label_component(tmp_path):
    from src.memory_store import init_memory_db, query_slack_memory_context, record_memory_item

    db_path = tmp_path / "leadsync.db"
    init_memory_db(str(db_path))

    record_memory_item(
        db_path=str(db_path),
        workflow="workflow1",
        item_type="ticket_enrichment",
        ticket_key="LEADS-123",
        project_key="LEADS",
        label="backend",
        component="auth",
        summary="Prompt guidance for LEADS-123",
    )
    record_memory_item(
        db_path=str(db_path),
        workflow="workflow2",
        item_type="daily_digest_area",
        project_key="LEADS",
        summary="Auth area: merged retry middleware",
        decision="Monitor token expiry metrics.",
    )
    record_memory_item(
        db_path=str(db_path),
        workflow="workflow3",
        item_type="slack_qa",
        ticket_key="LEADS-110",
        project_key="LEADS",
        label="backend",
        component="auth",
        summary="Use request-scoped session validation.",
        context={"question": "Should we cache sessions?"},
    )
    record_memory_item(
        db_path=str(db_path),
        workflow="workflow3",
        item_type="slack_qa",
        ticket_key="LEADS-111",
        project_key="LEADS",
        label="backend",
        component="billing",
        summary="Billing-specific guidance",
        context={"question": "Billing retry policy?"},
    )

    text = query_slack_memory_context(
        db_path=str(db_path),
        ticket_key="LEADS-123",
        project_key="LEADS",
        label="backend",
        component="auth",
        digest_days=7,
        similar_limit=5,
    )

    assert "Ticket Memory" in text
    assert "Recent Digest Signals" in text
    assert "Similar Q&A" in text
    assert "LEADS-110" in text
    assert "LEADS-111" not in text


def test_query_leader_rules_returns_formatted_rules(tmp_path):
    from src.memory_store import init_memory_db, query_leader_rules, record_memory_item

    db_path = tmp_path / "leadsync.db"
    init_memory_db(str(db_path))

    record_memory_item(
        db_path=str(db_path),
        workflow="slack_prefs",
        item_type="leader_rule",
        summary="Always use TypeScript",
    )
    record_memory_item(
        db_path=str(db_path),
        workflow="slack_prefs",
        item_type="leader_rule",
        summary="Prefer functional components",
    )

    result = query_leader_rules(str(db_path))
    assert "General Leader Rules:" in result
    assert "- Always use TypeScript" in result
    assert "- Prefer functional components" in result


def test_query_leader_rules_returns_empty_when_no_rules(tmp_path):
    from src.memory_store import init_memory_db, query_leader_rules

    db_path = tmp_path / "leadsync.db"
    init_memory_db(str(db_path))

    result = query_leader_rules(str(db_path))
    assert result == ""


def test_acquire_idempotency_lock_is_insert_once(tmp_path):
    from src.memory_store import acquire_idempotency_lock, init_memory_db

    db_path = tmp_path / "leadsync.db"
    init_memory_db(str(db_path))

    first = acquire_idempotency_lock(
        db_path=str(db_path),
        workflow="workflow2",
        lock_key="digest:2026-02-28T11:00:00Z:60",
    )
    second = acquire_idempotency_lock(
        db_path=str(db_path),
        workflow="workflow2",
        lock_key="digest:2026-02-28T11:00:00Z:60",
    )

    assert first is True
    assert second is False
