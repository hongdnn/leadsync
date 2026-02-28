"""
src/stream.py
WebSocket connection manager for streaming CrewAI output to the live dashboard.
Exports: stream_enabled, ConnectionManager, make_event, manager
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def stream_enabled() -> bool:
    """Return whether streaming is enabled via LEADSYNC_STREAM_ENABLED env var.

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
