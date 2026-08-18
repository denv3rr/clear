from __future__ import annotations

import hmac
import logging
import os
from typing import Optional

from fastapi import Header, HTTPException
from fastapi import WebSocket

LOGGER = logging.getLogger(__name__)
_UNSET_KEY_WARNED = False


def _expected_api_key() -> str:
    global _UNSET_KEY_WARNED
    expected = os.getenv("CLEAR_WEB_API_KEY", "")
    if expected:
        return expected
    if not _UNSET_KEY_WARNED:
        LOGGER.warning(
            "CLEAR_WEB_API_KEY is unset; API and WebSocket auth are open. "
            "Set a key for any shared or public deployment."
        )
        _UNSET_KEY_WARNED = True
    return ""


def _keys_match(provided: Optional[str], expected: str) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = _expected_api_key()
    if not expected:
        return
    if not _keys_match(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


def require_websocket_key(websocket: WebSocket) -> tuple[bool, Optional[str]]:
    expected = _expected_api_key()
    if not expected:
        return True, None
    api_key = websocket.headers.get("x-api-key")
    if _keys_match(api_key, expected):
        return True, None
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    for proto in protocols.split(","):
        candidate = proto.strip()
        prefix = "clear-key."
        if candidate.startswith(prefix) and _keys_match(candidate[len(prefix):].strip(), expected):
            return True, candidate
    return False, None
