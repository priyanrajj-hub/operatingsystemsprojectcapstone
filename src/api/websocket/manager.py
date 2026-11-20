"""
WebSocket connection manager for real-time telemetry and decision broadcasting.
"""

from __future__ import annotations

import logging

from starlette.websockets import WebSocket

from telemetry.schemas import LiveWebSocketMessage

logger = logging.getLogger("aidax.api.websocket")


class ConnectionManager:
    """Manages active client WebSocket connections and multiplexes broadcast channels."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register an incoming WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Total active: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                "WebSocket client disconnected. Total active: %d", len(self.active_connections)
            )

    async def broadcast(self, message: LiveWebSocketMessage) -> None:
        """Broadcast structured event to all active clients."""
        payload = message.model_dump_json()
        disconnected: list[WebSocket] = []

        for conn in self.active_connections:
            try:
                await conn.send_text(payload)
            except Exception:
                disconnected.append(conn)

        for dead_conn in disconnected:
            self.disconnect(dead_conn)
