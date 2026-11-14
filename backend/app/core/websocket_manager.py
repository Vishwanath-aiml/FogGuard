"""WebSocket connection manager for real-time dashboard updates.

OPTIMIZATION (Phase 3): Broadcast uses asyncio.gather() so all clients
receive data concurrently instead of sequentially.  One slow client no
longer blocks the others.
"""
import json
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WS client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WS client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast to all connected clients concurrently."""
        if not self.active_connections:
            return
        data = json.dumps(message, default=str)

        # OPTIMIZATION: fire all sends in parallel, collect exceptions
        results = await asyncio.gather(
            *[self._safe_send(conn, data) for conn in self.active_connections],
            return_exceptions=True,
        )

        # Clean up dead connections
        dead = [
            self.active_connections[i]
            for i, r in enumerate(results)
            if isinstance(r, Exception)
        ]
        for conn in dead:
            self.disconnect(conn)

    async def _safe_send(self, connection: WebSocket, data: str):
        """Send to a single client; raises on failure so gather() can catch it."""
        await connection.send_text(data)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        data = json.dumps(message, default=str)
        await websocket.send_text(data)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()
