import os

from fastapi.testclient import TestClient

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
