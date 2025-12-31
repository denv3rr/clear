import os

from fastapi.testclient import TestClient

from web_api.app import app

API_HEADERS = (
    {"X-API-Key": os.getenv("CLEAR_WEB_API_KEY")}
    if os.getenv("CLEAR_WEB_API_KEY")
    else {}
)

def test_trackers_websocket_stream():
    client = TestClient(app)
    with client.websocket_connect(
        "/ws/trackers?mode=combined&interval=1",
        headers=API_HEADERS,
    ) as websocket:
        payload = websocket.receive_json()
        assert isinstance(payload, dict)
        assert "points" in payload
