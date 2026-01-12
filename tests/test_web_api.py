import os
from unittest import mock

from fastapi.testclient import TestClient

from web_api import app as web_app
from web_api.routes import clients as clients_routes
from web_api.routes import intel as intel_routes
from web_api.routes import trackers as tracker_routes

def _api_headers():
    key = os.getenv("CLEAR_WEB_API_KEY")
    return {"X-API-Key": key} if key else {}


def test_health_endpoint():
    client = TestClient(web_app.app)
    resp = client.get("/api/health", headers=_api_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_settings_endpoint():
    client = TestClient(web_app.app)
    resp = client.get("/api/settings", headers=_api_headers())
    assert resp.status_code == 200
    payload = resp.json()
    assert "settings" in payload
    assert "credentials" in payload["settings"]
    assert "system" in payload
    assert "system_metrics" in payload


def test_client_index_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(clients_routes.DbClientStore, "fetch_all_clients") as mocked:
        mocked.return_value = [{"client_id": "c1", "name": "Test Client", "accounts": []}]
        resp = client.get("/api/clients", headers=_api_headers())
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["clients"]
    assert payload["clients"][0]["client_id"] == "c1"


def test_client_create_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(clients_routes.DbClientStore, "create_client") as mocked:
        mocked.return_value = {
            "client_id": "c1",
            "name": "Atlas Capital",
            "risk_profile": "Balanced",
            "accounts": [],
        }
        resp = client.post(
            "/api/clients",
            json={"client_id": "c1", "name": "Atlas Capital", "risk_profile": "Balanced", "accounts": []},
            headers=_api_headers(),
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["name"] == "Atlas Capital"


def test_client_update_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(clients_routes.DbClientStore, "update_client") as mocked:
        mocked.return_value = {
            "client_id": "c1",
            "name": "New Name",
            "risk_profile": "Balanced",
            "accounts": [],
        }
        resp = client.patch(
            "/api/clients/c1",
            json={"client_id": "c1", "name": "New Name", "risk_profile": "Balanced", "accounts": []},
            headers=_api_headers(),
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["name"] == "New Name"


def test_account_create_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(clients_routes.DbClientStore, "create_account") as mocked_create, mock.patch.object(
        clients_routes.DbClientStore, "fetch_client"
    ) as mocked_client:
        mocked_create.return_value = {
            "account_id": "a1",
            "account_name": "Primary Brokerage",
            "account_type": "Taxable",
            "holdings": {},
            "lots": {},
            "manual_holdings": [],
        }
        mocked_client.return_value = {"client_id": "c1", "name": "Test Client", "accounts": []}
        resp = client.post(
            "/api/clients/c1/accounts",
            json={"account_id": "a1", "account_name": "Primary Brokerage", "account_type": "Taxable", "tags": ["Core"]},
            headers=_api_headers(),
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["account"]["account_name"] == "Primary Brokerage"


def test_account_update_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(clients_routes.DbClientStore, "update_account") as mocked_update, mock.patch.object(
        clients_routes.DbClientStore, "fetch_client"
    ) as mocked_client:
        mocked_update.return_value = {
            "account_id": "a1",
            "account_name": "Alpha Prime",
            "account_type": "Taxable",
            "holdings": {},
            "lots": {},
            "manual_holdings": [],
            "custodian": "Fidelity",
        }
        mocked_client.return_value = {"client_id": "c1", "name": "Test Client", "accounts": []}
        resp = client.patch(
            "/api/clients/c1/accounts/a1",
            json={"account_id": "a1", "account_name": "Alpha Prime", "account_type": "Taxable", "custodian": "Fidelity"},
            headers=_api_headers(),
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["account"]["account_name"] == "Alpha Prime"


def test_diagnostics_endpoint():
    client = TestClient(web_app.app)
    resp = client.get("/api/tools/diagnostics", headers=_api_headers())
    assert resp.status_code == 200
    payload = resp.json()
    assert "system" in payload
    assert "metrics" in payload
    assert "feeds" in payload
    assert "registry" in payload["feeds"]
    assert "summary" in payload["feeds"]
    assert "health_counts" in payload["feeds"]["summary"]
    assert "duplicates" in payload
    assert "accounts" in payload["duplicates"]
    assert "orphans" in payload
    assert "holdings" in payload["orphans"]
    assert "lots" in payload["orphans"]


def test_intel_summary_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(intel_routes.MarketIntel, "combined_report") as mocked:
        mocked.return_value = {"title": "ok", "summary": [], "sections": []}
        resp = client.get("/api/intel/summary", headers=_api_headers())
    assert resp.status_code == 200
    assert resp.json()["title"] == "ok"


def test_intel_news_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(intel_routes.MarketIntel, "fetch_news_signals") as mocked:
        mocked.return_value = {"items": [{"title": "A"}], "cached": False, "stale": False, "skipped": []}
        resp = client.get("/api/intel/news?limit=1", headers=_api_headers())
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
        resp = client.get("/api/trackers/search?q=aal&mode=combined", headers=_api_headers())
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 1


def test_tracker_snapshot_endpoint_stubbed():
    client = TestClient(web_app.app)
    sample = {
        "mode": "combined",
        "count": 1,
        "warnings": [],
        "points": [{"id": "abc123", "kind": "flight", "label": "AAL762"}],
    }
    with mock.patch.object(tracker_routes.GlobalTrackers, "get_snapshot") as mocked:
        mocked.return_value = sample
        resp = client.get("/api/trackers/snapshot?mode=combined", headers=_api_headers())
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["points"]
    assert payload["count"] == len(payload["points"])


def test_tracker_snapshot_filters_stubbed():
    client = TestClient(web_app.app)
    sample = {
        "mode": "combined",
        "count": 2,
        "warnings": [],
        "points": [
            {
                "id": "abc123",
                "kind": "flight",
                "label": "AAL762",
                "category": "commercial",
                "country": "United States",
                "operator": "AAL",
                "operator_name": "American Airlines",
                "lat": 35.0,
                "lon": -120.0,
            },
            {
                "id": "ship-1",
                "kind": "ship",
                "label": "MSC TEST",
                "category": "cargo",
                "country": "Canada",
                "operator": "MSC",
                "operator_name": "MSC",
                "lat": 10.0,
                "lon": 10.0,
            },
        ],
    }
    with mock.patch.object(tracker_routes.GlobalTrackers, "get_snapshot") as mocked:
        mocked.return_value = sample
        resp = client.get(
            "/api/trackers/snapshot?mode=combined&category=commercial&country=united&operator=aal&bbox=30,-130,40,-110",
            headers=_api_headers(),
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 1
    assert payload["points"][0]["id"] == "abc123"


def test_tracker_snapshot_invalid_bbox():
    client = TestClient(web_app.app)
    resp = client.get(
        "/api/trackers/snapshot?bbox=1,2,3",
        headers=_api_headers(),
    )
    assert resp.status_code == 400
    assert "bbox" in resp.json()["detail"]


def test_tracker_detail_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(tracker_routes.GlobalTrackers, "get_detail") as mocked:
        mocked.return_value = {"id": "abc123", "point": {"label": "AAL762"}, "history": []}
        resp = client.get("/api/trackers/detail/abc123", headers=_api_headers())
    assert resp.status_code == 200
    assert resp.json()["point"]["label"] == "AAL762"

def test_tracker_history_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(tracker_routes.GlobalTrackers, "get_history") as mocked:
        mocked.return_value = {"id": "abc123", "history": [{"ts": 1, "lat": 10.0, "lon": 20.0}]}
        resp = client.get("/api/trackers/history/abc123", headers=_api_headers())
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["id"] == "abc123"
    assert payload["history"]


def test_tracker_analysis_endpoint_stubbed():
    client = TestClient(web_app.app)
    sample = {
        "id": "abc123",
        "replay": [{"ts": 1, "lat": 10.0, "lon": 20.0}],
        "loiter": {"detected": False},
        "geofences": {"events": [], "active": []},
    }
    with mock.patch.object(tracker_routes.GlobalTrackers, "analyze_tracker") as mocked:
        mocked.return_value = sample
        resp = client.get("/api/trackers/analysis/abc123", headers=_api_headers())
    assert resp.status_code == 200
    assert resp.json()["id"] == "abc123"


def test_tracker_analysis_custom_endpoint_stubbed():
    client = TestClient(web_app.app)
    sample = {
        "id": "abc123",
        "replay": [{"ts": 1, "lat": 10.0, "lon": 20.0}],
        "loiter": {"detected": False},
        "geofences": {"events": [], "active": []},
    }
    with mock.patch.object(tracker_routes.GlobalTrackers, "analyze_tracker") as mocked:
        mocked.return_value = sample
        resp = client.post(
            "/api/trackers/analysis",
            json={
                "tracker_id": "abc123",
                "window_sec": 3600,
                "loiter_radius_km": 10.0,
                "loiter_min_minutes": 20.0,
                "geofences": [
                    {"id": "f1", "label": "Test", "lat": 10.0, "lon": 20.0, "radius_km": 5.0}
                ],
            },
            headers=_api_headers(),
        )
    assert resp.status_code == 200
    assert resp.json()["id"] == "abc123"


def test_client_dashboard_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(clients_routes.DbClientStore, "fetch_client") as mocked_client, mock.patch.object(
        clients_routes, "portfolio_dashboard"
    ) as mocked_dash:
        mocked_client.return_value = {"client_id": "c1", "name": "Test Client", "accounts": []}
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
        resp = client.get("/api/clients/c1/dashboard?interval=1M", headers=_api_headers())
    assert resp.status_code == 200
    assert resp.json()["client"]["client_id"] == "c1"


def test_account_dashboard_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(clients_routes.DbClientStore, "fetch_client") as mocked_client, mock.patch.object(
        clients_routes, "account_dashboard"
    ) as mocked_dash:
        mocked_client.return_value = {
            "client_id": "c1",
            "name": "Test Client",
            "accounts": [{"account_id": "a1", "account_name": "Alpha", "holdings": {}}],
        }
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
        resp = client.get("/api/clients/c1/accounts/a1/dashboard?interval=1M", headers=_api_headers())
    assert resp.status_code == 200
    assert resp.json()["account"]["account_id"] == "a1"


def test_client_patterns_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(clients_routes.DbClientStore, "fetch_client") as mocked_client, mock.patch.object(
        clients_routes, "client_patterns"
    ) as mocked_patterns:
        mocked_client.return_value = {"client_id": "c1", "name": "Test Client", "accounts": []}
        mocked_patterns.return_value = {"entropy": 0.1, "wave_surface": {"z": []}}
        resp = client.get("/api/clients/c1/patterns?interval=1M", headers=_api_headers())
    assert resp.status_code == 200
    assert "entropy" in resp.json()


def test_account_patterns_endpoint_stubbed():
    client = TestClient(web_app.app)
    with mock.patch.object(clients_routes.DbClientStore, "fetch_client") as mocked_client, mock.patch.object(
        clients_routes, "account_patterns"
    ) as mocked_patterns:
        mocked_client.return_value = {
            "client_id": "c1",
            "name": "Test Client",
            "accounts": [{"account_id": "a1", "account_name": "Alpha", "holdings": {}}],
        }
        mocked_patterns.return_value = {"entropy": 0.1, "wave_surface": {"z": []}}
        resp = client.get("/api/clients/c1/accounts/a1/patterns?interval=1M", headers=_api_headers())
    assert resp.status_code == 200
    assert "entropy" in resp.json()
