"""
src/stream.py
WebSocket connection manager for streaming CrewAI output to the live dashboard.
Exports: stream_enabled, ConnectionManager, make_event, make_crew_callbacks, manager
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def stream_enabled() -> bool:
    """Return whether dashboard streaming is enabled via LEADSYNC_STREAM_ENABLED.

    Returns:
        True unless env var is set to a falsy value.
    """
    value = os.getenv("LEADSYNC_STREAM_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def make_event(
    event_type: str,
    workflow: str,
    *,
    agent_role: str = "",
    task_name: str = "",
    content: str = "",
    chunk_type: str = "",
    tool_name: str = "",
) -> dict[str, Any]:
    """Build a standardized event dict for WebSocket broadcast.

    Args:
        event_type: Event category (workflow_start, chunk, tool_call, workflow_end, workflow_error).
        workflow: Workflow label (e.g. 'WF1-Enrichment').
        agent_role: CrewAI agent role name.
        task_name: Task description snippet.
        content: Text content of the chunk.
        chunk_type: Type of chunk (text, tool_call).
        tool_name: Name of tool being invoked (for tool_call chunks).
    Returns:
        Dict ready for JSON serialization.
    """
    return {
        "type": event_type,
        "workflow": workflow,
        "agent_role": agent_role,
        "task_name": task_name,
        "content": content,
        "chunk_type": chunk_type,
        "tool_name": tool_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class ConnectionManager:
    """Manages WebSocket connections and provides thread-safe broadcast."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store the asyncio event loop reference for cross-thread broadcasts.

        Args:
            loop: The running FastAPI event loop.
        """
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a WebSocket connection.

        Args:
            ws: Incoming WebSocket to accept.
        """
        await ws.accept()
        self._connections.append(ws)
        logger.info("WebSocket connected. Total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket connection from the pool.

        Args:
            ws: WebSocket to remove.
        """
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info("WebSocket disconnected. Total: %d", len(self._connections))

    async def _broadcast(self, data: dict[str, Any]) -> None:
        """Send data to all connected WebSockets, removing dead connections.

        Args:
            data: Dict to serialize as JSON and send.
        """
        if not self._connections:
            return
        message = json.dumps(data)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_event(self, data: dict[str, Any]) -> None:
        """Async broadcast — called from async endpoint handlers.

        Args:
            data: Event dict to broadcast.
        """
        await self._broadcast(data)

    def broadcast_sync(self, data: dict[str, Any]) -> None:
        """Thread-safe broadcast — called from CrewAI execution threads.

        Uses asyncio.run_coroutine_threadsafe to bridge sync→async.
        Non-blocking: does not wait for send to complete.

        Args:
            data: Event dict to broadcast.
        """
        if not self._loop or not self._connections:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(data), self._loop)
        except RuntimeError:
            logger.debug("Event loop closed; skipping broadcast.")


manager = ConnectionManager()


def _make_step_callback(label: str) -> Callable[..., None]:
    """Create a step_callback that broadcasts each agent step to the dashboard.

    Args:
        label: Workflow label (e.g. 'WF1-Enrichment').
    Returns:
        Callback function suitable for CrewAI Crew(step_callback=...).
    """
    def _cb(step_output: Any) -> None:
        agent_role = str(getattr(step_output, "agent", "") or "")
        tool_name = str(getattr(step_output, "tool", "") or "")
        content = ""
        for attr in ("log", "text", "output", "result"):
            val = getattr(step_output, attr, None)
            if val:
                content = str(val)
                break
        if not content:
            content = str(step_output)[:500]
        event_type = "tool_call" if tool_name else "chunk"
        manager.broadcast_sync(make_event(
            event_type, label,
            agent_role=agent_role,
            content=content,
            tool_name=tool_name,
        ))
    return _cb


def _make_task_callback(label: str) -> Callable[..., None]:
    """Create a task_callback that broadcasts task completion to the dashboard.

    Args:
        label: Workflow label (e.g. 'WF1-Enrichment').
    Returns:
        Callback function suitable for CrewAI Crew(task_callback=...).
    """
    def _cb(task_output: Any) -> None:
        agent_role = str(getattr(task_output, "agent", "") or "")
        summary = str(getattr(task_output, "summary", "") or "")
        raw = str(getattr(task_output, "raw", "") or "")
        content = summary or raw[:500]
        task_name = str(getattr(task_output, "description", "") or "")
        manager.broadcast_sync(make_event(
            "task_complete", label,
            agent_role=agent_role,
            content=content,
            task_name=task_name[:120],
        ))
    return _cb


def make_crew_callbacks(label: str) -> dict[str, Any]:
    """Return step_callback and task_callback kwargs for a Crew constructor.

    Returns empty dict when streaming is disabled, so Crew() works unchanged.

    Args:
        label: Workflow label for event metadata.
    Returns:
        Dict with 'step_callback' and 'task_callback' keys, or empty dict.
    """
    if not stream_enabled():
        return {}
    return {
        "step_callback": _make_step_callback(label),
        "task_callback": _make_task_callback(label),
    }
