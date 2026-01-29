import os

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from web_api.app import app

def _api_headers() -> dict:
    api_key = os.getenv("CLEAR_WEB_API_KEY")
    if api_key:
        return {"X-API-Key": api_key}
    return {}

def test_trackers_websocket_stream():
    client = TestClient(app)
    with client.websocket_connect(
        "/ws/trackers?mode=combined&interval=1",
        headers=_api_headers(),
    ) as websocket:
        payload = websocket.receive_json()
        assert isinstance(payload, dict)
        assert "points" in payload


def test_trackers_websocket_rejects_missing_key(monkeypatch):
    monkeypatch.setenv("CLEAR_WEB_API_KEY", "secret")
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/trackers?mode=combined&interval=1"):
            pass


def test_trackers_websocket_accepts_subprotocol_key(monkeypatch):
    monkeypatch.setenv("CLEAR_WEB_API_KEY", "secret")
    client = TestClient(app)
    with client.websocket_connect(
        "/ws/trackers?mode=combined&interval=1",
        headers={"sec-websocket-protocol": "clear-key.secret"},
    ) as websocket:
        payload = websocket.receive_json()
        assert isinstance(payload, dict)
