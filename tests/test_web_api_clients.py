import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core import models
from web_api.app import app
from web_api.routes.clients import get_db

DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture()
def session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture()
def client(session):
    def override_get_db():
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_db] = override_get_db
    os.environ["CLEAR_WEB_API_KEY"] = "test_key"
    yield TestClient(app, headers={"X-API-Key": "test_key"})

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
