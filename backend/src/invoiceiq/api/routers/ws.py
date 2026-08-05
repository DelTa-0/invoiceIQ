"""WebSocket endpoint for real-time extraction progress."""

from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..deps import Principal, get_principal
from ..websocket.manager import get_ws_manager

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/sessions/{session_id}")
async def session_ws(
    session_id: str,
    websocket: WebSocket,
    _principal: Principal = Depends(get_principal),
) -> None:
    manager = get_ws_manager()
    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)