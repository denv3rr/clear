from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException
from fastapi import WebSocket


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("CLEAR_WEB_API_KEY", "")
    if not expected:
        return
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


def require_websocket_key(websocket: WebSocket) -> bool:
    expected = os.getenv("CLEAR_WEB_API_KEY", "")
    if not expected:
        return True
    api_key = websocket.headers.get("x-api-key") or websocket.query_params.get("api_key")
    return bool(api_key and api_key == expected)
