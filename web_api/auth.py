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


def require_websocket_key(websocket: WebSocket) -> tuple[bool, Optional[str]]:
    expected = os.getenv("CLEAR_WEB_API_KEY", "")
    if not expected:
        return True, None
    api_key = websocket.headers.get("x-api-key")
    if api_key and api_key == expected:
        return True, None
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    for proto in protocols.split(","):
        candidate = proto.strip()
        if candidate.startswith("clear-key.") and candidate[len("clear-key."):].strip() == expected:
            return True, candidate
    return False, None
