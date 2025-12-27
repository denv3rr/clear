from unittest import mock

from fastapi.testclient import TestClient

from web_api import app as web_app
from web_api.routes import intel as intel_routes
from web_api.routes import trackers as tracker_routes


def test_health_endpoint():
    client = TestClient(web_app.app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_settings_endpoint():
    client = TestClient(web_app.app)
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    payload = resp.json()
    assert "settings" in payload
    assert "credentials" in payload["settings"]


def test_diagnostics_endpoint():
    client = TestClient(web_app.app)
    resp = client.get("/api/tools/diagnostics")
    assert resp.status_code == 200
    payload = resp.json()
    assert "system" in payload
    assert "disk" in payload


def test_intel_summary_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(intel_routes.MarketIntel, "combined_report") as mocked:
        mocked.return_value = {"title": "ok", "summary": [], "sections": []}
        resp = client.get("/api/intel/summary")
    assert resp.status_code == 200
    assert resp.json()["title"] == "ok"


def test_intel_news_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(intel_routes.MarketIntel, "fetch_news_signals") as mocked:
        mocked.return_value = {"items": [{"title": "A"}], "cached": False, "stale": False, "skipped": []}
        resp = client.get("/api/intel/news?limit=1")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["items"]


def test_tracker_search_endpoint_stubbed():
    client = TestClient(web_app.app)
    sample = {
        "points": [
            {
                "id": "abc123",
                "kind": "flight",
                "label": "AAL762",
                "category": "commercial",
                "operator": "AAL",
                "flight_number": "762",
                "tail_number": "N123AA",
                "country": "United States",
            }
        ]
    }
    with mock.patch.object(tracker_routes.GlobalTrackers, "get_snapshot") as mocked:
        mocked.return_value = sample
        resp = client.get("/api/trackers/search?q=aal&mode=combined")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 1


def test_tracker_detail_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(tracker_routes.GlobalTrackers, "get_detail") as mocked:
        mocked.return_value = {"id": "abc123", "point": {"label": "AAL762"}, "history": []}
        resp = client.get("/api/trackers/detail/abc123")
    assert resp.status_code == 200
    assert resp.json()["point"]["label"] == "AAL762"
