from fastapi.testclient import TestClient

from web_api.app import app


def test_trackers_websocket_stream():
    client = TestClient(app)
    with client.websocket_connect("/ws/trackers?mode=combined&interval=1") as websocket:
        payload = websocket.receive_json()
        assert isinstance(payload, dict)
        assert "points" in payload
