from unittest import mock

from fastapi.testclient import TestClient

from web_api import app as web_app
from web_api.routes import clients as clients_routes
from web_api.routes import intel as intel_routes
from web_api.routes import trackers as tracker_routes
from modules.client_mgr.client_model import Client, Account


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


def test_client_dashboard_endpoint_stubbed():
    client = TestClient(web_app.app)
    fake_client = Client(client_id="c1", name="Test Client", accounts=[])
    with mock.patch.object(clients_routes.DataHandler, "load_clients") as mocked_load, mock.patch.object(
        clients_routes, "portfolio_dashboard"
    ) as mocked_dash:
        mocked_load.return_value = [fake_client]
        mocked_dash.return_value = {
            "client": {"client_id": "c1"},
            "totals": {},
            "holdings": [],
            "manual_holdings": [],
            "history": [],
            "risk": {},
            "regime": {},
            "warnings": [],
        }
        resp = client.get("/api/clients/c1/dashboard?interval=1M")
    assert resp.status_code == 200
    assert resp.json()["client"]["client_id"] == "c1"


def test_account_dashboard_endpoint_stubbed():
    client = TestClient(web_app.app)
    account = Account(account_id="a1", account_name="Alpha")
    fake_client = Client(client_id="c1", name="Test Client", accounts=[account])
    with mock.patch.object(clients_routes.DataHandler, "load_clients") as mocked_load, mock.patch.object(
        clients_routes, "account_dashboard"
    ) as mocked_dash:
        mocked_load.return_value = [fake_client]
        mocked_dash.return_value = {
            "client": {"client_id": "c1"},
            "account": {"account_id": "a1"},
            "totals": {},
            "holdings": [],
            "manual_holdings": [],
            "history": [],
            "risk": {},
            "regime": {},
            "warnings": [],
        }
        resp = client.get("/api/clients/c1/accounts/a1/dashboard?interval=1M")
    assert resp.status_code == 200
    assert resp.json()["account"]["account_id"] == "a1"


def test_client_patterns_endpoint_stubbed():
    client = TestClient(web_app.app)
    fake_client = Client(client_id="c1", name="Test Client", accounts=[])
    with mock.patch.object(clients_routes.DataHandler, "load_clients") as mocked_load, mock.patch.object(
        clients_routes, "client_patterns"
    ) as mocked_patterns:
        mocked_load.return_value = [fake_client]
        mocked_patterns.return_value = {"entropy": 0.1, "wave_surface": {"z": []}}
        resp = client.get("/api/clients/c1/patterns?interval=1M")
    assert resp.status_code == 200
    assert "entropy" in resp.json()


def test_account_patterns_endpoint_stubbed():
    client = TestClient(web_app.app)
    account = Account(account_id="a1", account_name="Alpha")
    fake_client = Client(client_id="c1", name="Test Client", accounts=[account])
    with mock.patch.object(clients_routes.DataHandler, "load_clients") as mocked_load, mock.patch.object(
        clients_routes, "account_patterns"
    ) as mocked_patterns:
        mocked_load.return_value = [fake_client]
        mocked_patterns.return_value = {"entropy": 0.1, "wave_surface": {"z": []}}
        resp = client.get("/api/clients/c1/accounts/a1/patterns?interval=1M")
    assert resp.status_code == 200
    assert "entropy" in resp.json()
