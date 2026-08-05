"""WebSocket connection manager for real-time extraction progress."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Tracks active WebSocket connections per session and broadcasts events."""

    def __init__(self) -> None:
        self._connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id][id(websocket)] = websocket

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        self._connections[session_id].pop(id(websocket), None)

    async def broadcast(self, session_id: str, event: dict[str, Any]) -> None:
        message = json.dumps(event)
        disconnected: list[int] = []
        for ws_id, ws in self._connections[session_id].items():
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws_id)
        for ws_id in disconnected:
            self._connections[session_id].pop(ws_id, None)

    async def send(self, session_id: str, websocket: WebSocket, event: dict[str, Any]) -> None:
        message = json.dumps(event)
        try:
            await websocket.send_text(message)
        except Exception:
            self.disconnect(session_id, websocket)

    def active_sessions(self) -> list[str]:
        return [sid for sid, conns in self._connections.items() if conns]


_manager: ConnectionManager | None = None


def get_ws_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager