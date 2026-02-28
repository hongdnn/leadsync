"""Shared pytest fixtures for LeadSync test suite."""

import pytest


@pytest.fixture(autouse=True)
def _disable_memory_side_effects(monkeypatch):
    """Disable workflow memory by default in tests unless explicitly overridden."""
    monkeypatch.setenv("LEADSYNC_MEMORY_ENABLED", "false")
