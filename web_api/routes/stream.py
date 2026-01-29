from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from modules.market_data.trackers import GlobalTrackers
from web_api.auth import require_websocket_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


@router.websocket("/ws/trackers")
async def trackers_stream(websocket: WebSocket, mode: Optional[str] = None, interval: int = 5):
    ok, subprotocol = require_websocket_key(websocket)
    if not ok:
        await websocket.close(code=1008, reason="Invalid API key")
        return
    await websocket.accept(subprotocol=subprotocol)
    trackers = GlobalTrackers()
    stream_mode = mode or "combined"
    stream_interval = max(1, min(int(interval or 5), 60))
    try:
        while True:
            payload = trackers.get_snapshot(mode=stream_mode)
            warnings = list(payload.get("warnings", []) or [])
            warnings = validate_payload(
                payload,
                required_keys=("mode", "count", "points"),
                non_empty_keys=("points",),
                warnings=warnings,
            )
            attach_meta(
                payload,
                route="/ws/trackers",
                source="trackers_stream",
                warnings=warnings,
            )
            await websocket.send_json(payload)
            await asyncio.sleep(stream_interval)
    except WebSocketDisconnect:
        return
