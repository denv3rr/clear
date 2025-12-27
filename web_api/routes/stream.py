from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from modules.market_data.trackers import GlobalTrackers
from web_api.auth import require_websocket_key

router = APIRouter()


@router.websocket("/ws/trackers")
async def trackers_stream(websocket: WebSocket, mode: Optional[str] = None, interval: int = 5):
    await websocket.accept()
    if not require_websocket_key(websocket):
        await websocket.close(code=1008)
        return
    trackers = GlobalTrackers()
    stream_mode = mode or "combined"
    stream_interval = max(1, min(int(interval or 5), 60))
    try:
        while True:
            payload = trackers.get_snapshot(mode=stream_mode)
            await websocket.send_json(payload)
            await asyncio.sleep(stream_interval)
    except WebSocketDisconnect:
        return
