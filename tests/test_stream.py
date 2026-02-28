"""Unit tests for src/stream.py — stream_enabled, make_event, ConnectionManager."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_stream_enabled_default_true():
    """stream_enabled returns True when env var is absent."""
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("LEADSYNC_STREAM_ENABLED", None)
        from src.stream import stream_enabled
        assert stream_enabled() is True


def test_stream_enabled_explicit_false():
    """stream_enabled returns False for falsy env values."""
    from src.stream import stream_enabled
    for val in ("false", "0", "no", "off", "FALSE"):
        with patch.dict(os.environ, {"LEADSYNC_STREAM_ENABLED": val}):
            assert stream_enabled() is False


def test_stream_enabled_explicit_true():
    """stream_enabled returns True for truthy values."""
    from src.stream import stream_enabled
    with patch.dict(os.environ, {"LEADSYNC_STREAM_ENABLED": "true"}):
        assert stream_enabled() is True


def test_make_event_returns_expected_fields():
    """make_event builds a dict with all required fields."""
    from src.stream import make_event
    ev = make_event(
        "workflow_start",
        "WF1-Enrichment",
        agent_role="Context Gatherer",
        content="Starting...",
    )
    assert ev["type"] == "workflow_start"
    assert ev["workflow"] == "WF1-Enrichment"
    assert ev["agent_role"] == "Context Gatherer"
    assert ev["content"] == "Starting..."
    assert ev["task_name"] == ""
    assert ev["chunk_type"] == ""
    assert ev["tool_name"] == ""
    assert "timestamp" in ev


def test_make_event_minimal():
    """make_event works with only required positional args."""
    from src.stream import make_event
    ev = make_event("chunk", "WF2")
    assert ev["type"] == "chunk"
    assert ev["workflow"] == "WF2"


def test_connection_manager_broadcast_sync_without_loop():
    """broadcast_sync is a no-op when no event loop is set."""
    from src.stream import ConnectionManager
    mgr = ConnectionManager()
    mgr.broadcast_sync({"type": "test"})


def test_connection_manager_broadcast_sync_without_connections():
    """broadcast_sync is a no-op when no connections exist."""
    from src.stream import ConnectionManager
    mgr = ConnectionManager()
    mgr.set_loop(MagicMock())
    mgr.broadcast_sync({"type": "test"})


@pytest.mark.asyncio
async def test_connection_manager_connect_disconnect():
    """connect/disconnect manages the connection list."""
    from src.stream import ConnectionManager
    mgr = ConnectionManager()
    ws = AsyncMock()
    await mgr.connect(ws)
    assert len(mgr._connections) == 1
    ws.accept.assert_awaited_once()
    mgr.disconnect(ws)
    assert len(mgr._connections) == 0


@pytest.mark.asyncio
async def test_connection_manager_broadcast_event():
    """broadcast_event sends JSON to all connected sockets."""
    from src.stream import ConnectionManager
    mgr = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await mgr.connect(ws1)
    await mgr.connect(ws2)
    await mgr.broadcast_event({"type": "test"})
    assert ws1.send_text.await_count == 1
    assert ws2.send_text.await_count == 1
    sent = ws1.send_text.call_args[0][0]
    assert '"type": "test"' in sent


@pytest.mark.asyncio
async def test_broadcast_event_removes_dead_connections():
    """Dead WebSocket connections are removed during broadcast."""
    from src.stream import ConnectionManager
    mgr = ConnectionManager()
    ws_alive = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_text.side_effect = RuntimeError("closed")
    await mgr.connect(ws_alive)
    await mgr.connect(ws_dead)
    assert len(mgr._connections) == 2
    await mgr.broadcast_event({"type": "test"})
    assert len(mgr._connections) == 1
    assert ws_alive in mgr._connections


def test_make_crew_callbacks_returns_callbacks_when_enabled():
    """make_crew_callbacks returns step_callback and task_callback when enabled."""
    from src.stream import make_crew_callbacks
    with patch.dict(os.environ, {"LEADSYNC_STREAM_ENABLED": "true"}):
        cbs = make_crew_callbacks("WF1-Enrichment")
    assert "step_callback" in cbs
    assert "task_callback" in cbs
    assert callable(cbs["step_callback"])
    assert callable(cbs["task_callback"])


def test_make_crew_callbacks_returns_empty_when_disabled():
    """make_crew_callbacks returns empty dict when streaming is disabled."""
    from src.stream import make_crew_callbacks
    with patch.dict(os.environ, {"LEADSYNC_STREAM_ENABLED": "false"}):
        cbs = make_crew_callbacks("WF1-Enrichment")
    assert cbs == {}


def test_step_callback_broadcasts_chunk():
    """Step callback broadcasts a chunk event via manager."""
    from src.stream import make_crew_callbacks, manager
    with patch.dict(os.environ, {"LEADSYNC_STREAM_ENABLED": "true"}), \
         patch.object(manager, "broadcast_sync") as mock_bc:
        cbs = make_crew_callbacks("WF1-Test")
        step_output = MagicMock()
        step_output.agent = "Context Gatherer"
        step_output.tool = ""
        step_output.log = "Thinking about the task..."
        cbs["step_callback"](step_output)
        mock_bc.assert_called_once()
        event = mock_bc.call_args[0][0]
        assert event["type"] == "chunk"
        assert event["workflow"] == "WF1-Test"
        assert event["agent_role"] == "Context Gatherer"
        assert "Thinking" in event["content"]


def test_step_callback_broadcasts_tool_call():
    """Step callback broadcasts a tool_call event when tool is present."""
    from src.stream import make_crew_callbacks, manager
    with patch.dict(os.environ, {"LEADSYNC_STREAM_ENABLED": "true"}), \
         patch.object(manager, "broadcast_sync") as mock_bc:
        cbs = make_crew_callbacks("WF6-Test")
        step_output = MagicMock()
        step_output.agent = "Scanner"
        step_output.tool = "GITHUB_LIST_COMMITS"
        step_output.log = "Calling GitHub API"
        cbs["step_callback"](step_output)
        event = mock_bc.call_args[0][0]
        assert event["type"] == "tool_call"
        assert event["tool_name"] == "GITHUB_LIST_COMMITS"


def test_task_callback_broadcasts_task_complete():
    """Task callback broadcasts a task_complete event."""
    from src.stream import make_crew_callbacks, manager
    with patch.dict(os.environ, {"LEADSYNC_STREAM_ENABLED": "true"}), \
         patch.object(manager, "broadcast_sync") as mock_bc:
        cbs = make_crew_callbacks("WF2-Test")
        task_output = MagicMock()
        task_output.agent = "Digest Writer"
        task_output.summary = "Wrote the digest summary"
        task_output.raw = ""
        task_output.description = "Draft a detailed digest"
        cbs["task_callback"](task_output)
        event = mock_bc.call_args[0][0]
        assert event["type"] == "task_complete"
        assert event["workflow"] == "WF2-Test"
        assert event["agent_role"] == "Digest Writer"
        assert "digest summary" in event["content"]
