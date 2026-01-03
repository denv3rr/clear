import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
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
        json={"name": "Test Client", "risk_profile": "High"},
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
    client.post(
        "/api/clients",
        json={"name": "Client With Accounts", "risk_profile": "Medium"},
    )
    
    # Get the client ID
    response = client.get("/api/clients")
    client_id = response.json()["clients"][0]["client_id"]

    # Create an account for the client
    client.post(
        f"/api/clients/{client_id}/accounts",
        json={"account_name": "Checking Account", "account_type": "Checking"},
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
    response = client.post(
        "/api/clients",
        json={"name": "Meta Client", "risk_profile": "Moderate", "tax_profile": {"reporting_currency": "EUR"}},
    )
    client_id = response.json()["client_id"]
    account_payload = {
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
