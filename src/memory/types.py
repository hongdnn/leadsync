"""Dataclasses used by the SQLite memory layer."""

from dataclasses import dataclass
from typing import Any


@dataclass
class MemoryEvent:
    """Structured event payload persisted to the `events` table."""

    event_type: str
    workflow: str
    payload: dict[str, Any]
    ticket_key: str | None = None
    project_key: str | None = None
    label: str | None = None
    component: str | None = None


@dataclass
class MemoryItem:
    """Structured curated memory payload persisted to `memory_items`."""

    workflow: str
    item_type: str
    summary: str
    ticket_key: str | None = None
    project_key: str | None = None
    label: str | None = None
    component: str | None = None
    repo_key: str | None = None
    team_key: str | None = None
    decision: str | None = None
    rules_applied: str | None = None
    context: dict[str, Any] | None = None
