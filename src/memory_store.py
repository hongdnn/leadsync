"""
src/memory_store.py
Compatibility facade for LeadSync SQLite memory helpers.
Exports: init_memory_db, record_event, record_memory_item, acquire_idempotency_lock, query_slack_memory_context, query_leader_rules
"""

from src.memory.query import query_leader_rules, query_slack_memory_context
from src.memory.schema import init_memory_db
from src.memory.types import MemoryEvent, MemoryItem
from src.memory.write import acquire_idempotency_lock, record_event, record_memory_item

__all__ = [
    "MemoryEvent",
    "MemoryItem",
    "init_memory_db",
    "record_event",
    "record_memory_item",
    "acquire_idempotency_lock",
    "query_slack_memory_context",
    "query_leader_rules",
]
