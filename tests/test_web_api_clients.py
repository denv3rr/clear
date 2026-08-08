import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core import models
from web_api.app import app
from web_api.routes.clients import get_db


TEST_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "test_runtime" / "web_api_clients"


def _isolated_db_path(request, filename: str) -> Path:
    TEST_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    case_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.nodeid)
    case_dir = TEST_RUNTIME_DIR / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    db_path = case_dir / filename
    for suffix in ("", "-journal", "-shm", "-wal"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()
    return db_path


def _cleanup_sqlite_files(db_path: Path) -> None:
    for suffix in ("", "-journal", "-shm", "-wal"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()
    try:
        db_path.parent.rmdir()
    except OSError:
        pass


@pytest.fixture()
def session(request):
    db_path = _isolated_db_path(request, "clients.db")
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        _cleanup_sqlite_files(db_path)

@pytest.fixture()
def client(session, monkeypatch):
    def override_get_db():
        yield session
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setenv("CLEAR_WEB_API_KEY", "test_key")
    try:
        yield TestClient(app, headers={"X-API-Key": "test_key"})
    finally:
        app.dependency_overrides.pop(get_db, None)

def test_create_client(client):
    response = client.post(
        "/api/clients",
        json={"client_id": "test_client_1", "name": "Test Client", "risk_profile": "High", "accounts": []},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Client"
    assert data["risk_profile"] == "High"
    assert "client_id" in data


def test_create_client_without_id(client):
    response = client.post(
        "/api/clients",
        json={"name": "Auto ID Client", "risk_profile": "Low", "accounts": []},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Auto ID Client"
    assert data["client_id"]


def test_create_client_rejects_duplicate_normalized_name(client):
    response = client.post(
        "/api/clients",
        json={"client_id": "atlas-1", "name": "Atlas Capital", "accounts": []},
    )
    assert response.status_code == 200
    response = client.post(
        "/api/clients",
        json={"client_id": "atlas-2", "name": " atlas   capital ", "accounts": []},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["existing_client_id"] == "atlas-1"

def test_get_clients(client):
    response = client.get("/api/clients")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["clients"], list)

def test_get_clients_with_accounts(client):
    # Create a client
    client_id = "test_client_2"
    client.post(
        "/api/clients",
        json={"client_id": client_id, "name": "Client With Accounts", "risk_profile": "Medium", "accounts": []},
    )
    
    # Create an account for the client
    client.post(
        f"/api/clients/{client_id}/accounts",
        json={"account_id": "test_account_1", "account_name": "Checking Account", "account_type": "Checking"},
    )

    # Get clients again and assert the new client and its account are present
    response = client.get("/api/clients")
    assert response.status_code == 200
    data = response.json()
    
    found_client = None
    for c in data["clients"]:
        if c["name"] == "Client With Accounts":
            found_client = c
            break
    
    assert found_client is not None
    assert found_client["accounts_count"] == 1


def test_create_account_without_id(client):
    client_id = "test_client_4"
    client.post(
        "/api/clients",
        json={"client_id": client_id, "name": "Accountless", "risk_profile": "Low", "accounts": []},
    )
    response = client.post(
        f"/api/clients/{client_id}/accounts",
        json={"account_name": "Auto Account", "account_type": "Taxable"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["account"]["account_id"]


def test_create_account_rejects_duplicate_identity(client):
    client_id = "dup_account_client"
    client.post(
        "/api/clients",
        json={"client_id": client_id, "name": "Duplicate Account Client", "risk_profile": "Low", "accounts": []},
    )
    response = client.post(
        f"/api/clients/{client_id}/accounts",
        json={
            "account_id": "acct-1",
            "account_name": "Primary",
            "account_type": "Taxable",
            "ownership_type": "Individual",
            "custodian": "Fidelity",
        },
    )
    assert response.status_code == 200
    response = client.post(
        f"/api/clients/{client_id}/accounts",
        json={
            "account_id": "acct-2",
            "account_name": " primary ",
            "account_type": "Taxable",
            "ownership_type": "Individual",
            "custodian": " fidelity ",
        },
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["existing_account_id"] == "acct-1"


def test_account_metadata_persists(client):
    client_id = "test_client_3"
    response = client.post(
        "/api/clients",
        json={"client_id": client_id, "name": "Meta Client", "risk_profile": "Moderate", "tax_profile": {"reporting_currency": "EUR"}, "accounts": []},
    )
    
    account_payload = {
        "account_id": "test_account_2",
        "account_name": "Main",
        "account_type": "Taxable",
        "ownership_type": "Joint",
        "custodian": "Fidelity",
        "tags": ["Core", "LongTerm"],
        "tax_settings": {"jurisdiction": "US", "account_currency": "USD"},
        "holdings": {"AAPL": 2.5},
        "lots": {"AAPL": [{"qty": 2.5, "basis": 100.0, "timestamp": "2024-01-02T00:00:00"}]},
        "manual_holdings": [{"name": "Real Estate", "total_value": 1234.5}],
    }
    resp = client.post(f"/api/clients/{client_id}/accounts", json=account_payload)
    assert resp.status_code == 200
    payload = resp.json()
    account = payload["account"]
    assert account["custodian"] == "Fidelity"
    assert "AAPL" in account["holdings"]
    assert account["lots"]["AAPL"][0]["basis"] == 100.0
    assert account["manual_holdings"][0]["total_value"] == 1234.5


def test_duplicate_account_cleanup(client, session):
    dup_client = models.Client(client_uid="dup1", name="Dup Client")
    session.add(dup_client)
    session.flush()
    account_payload = dict(
        name="Primary",
        account_type="Taxable",
        ownership_type="Individual",
        custodian="Fidelity",
        tags=["Core"],
        tax_settings={"jurisdiction": "US"},
        holdings_map={"AAPL": 1.0},
        lots={"AAPL": [{"qty": 1.0, "basis": 100.0, "timestamp": "2024-01-01T00:00:00"}]},
        manual_holdings=[],
        extra={"source": "seed"},
        current_value=100.0,
        active_interval="1M",
        client_id=dup_client.id,
    )
    session.add(models.Account(account_uid="dup-a1", **account_payload))
    session.add(models.Account(account_uid="dup-a2", **account_payload))
    session.commit()

    response = client.get("/api/clients/duplicates")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["client_name_duplicates"]["count"] == 0

    response = client.post(
        "/api/clients/duplicates/cleanup",
        json={"confirm": True},
    )
    assert response.status_code == 200
    cleaned = response.json()
    assert cleaned["removed"] == 1
    assert cleaned["remaining"]["count"] == 0

    response = client.get("/api/clients/duplicates")
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_duplicate_client_names_are_reported(client, session):
    session.add(models.Client(client_uid="dup-client-a", name="Atlas Capital", name_key="atlas capital"))
    session.add(models.Client(client_uid="dup-client-b", name=" atlas   capital ", name_key="atlas capital"))
    session.commit()

    response = client.get("/api/clients/duplicates")
    assert response.status_code == 200
    payload = response.json()
    assert payload["client_name_duplicates"]["count"] == 1
    assert payload["client_name_duplicates"]["groups"] == 1


def test_update_account_rejects_duplicate_identity(client):
    client_id = "dup_patch_client"
    client.post(
        "/api/clients",
        json={"client_id": client_id, "name": "Duplicate Patch Client", "risk_profile": "Low", "accounts": []},
    )
    for payload in [
        {
            "account_id": "acct-1",
            "account_name": "Primary",
            "account_type": "Taxable",
            "ownership_type": "Individual",
            "custodian": "Fidelity",
        },
        {
            "account_id": "acct-2",
            "account_name": "Reserve",
            "account_type": "Taxable",
            "ownership_type": "Individual",
            "custodian": "Fidelity",
        },
    ]:
        response = client.post(f"/api/clients/{client_id}/accounts", json=payload)
        assert response.status_code == 200

    response = client.patch(
        f"/api/clients/{client_id}/accounts/acct-2",
        json={"account_name": " primary ", "custodian": " fidelity "},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["existing_account_id"] == "acct-1"
