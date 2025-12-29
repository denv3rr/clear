from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from modules.client_mgr.data_handler import DataHandler
from modules.client_mgr.client_model import Account, Client
from modules.view_models import (
    account_dashboard,
    account_detail,
    account_patterns,
    client_detail,
    client_patterns,
    list_clients,
    portfolio_dashboard,
)
from web_api.auth import require_api_key

router = APIRouter()


class ClientPayload(BaseModel):
    name: str = Field(..., min_length=1)
    risk_profile: Optional[str] = None
    tax_profile: Optional[Dict[str, Any]] = None


class ClientUpdatePayload(BaseModel):
    name: Optional[str] = None
    risk_profile: Optional[str] = None
    tax_profile: Optional[Dict[str, Any]] = None


class AccountPayload(BaseModel):
    account_name: str = Field(..., min_length=1)
    account_type: Optional[str] = None
    ownership_type: Optional[str] = None
    custodian: Optional[str] = None
    tags: Optional[List[str]] = None
    tax_settings: Optional[Dict[str, Any]] = None


class AccountUpdatePayload(BaseModel):
    account_name: Optional[str] = None
    account_type: Optional[str] = None
    ownership_type: Optional[str] = None
    custodian: Optional[str] = None
    tags: Optional[List[str]] = None
    tax_settings: Optional[Dict[str, Any]] = None


def _find_client(clients: List[Client], client_id: str) -> Client:
    for client in clients:
        if client.client_id == client_id:
            return client
    raise HTTPException(status_code=404, detail="Client not found")


def _find_account(client: Client, account_id: str) -> Account:
    for account in client.accounts:
        if account.account_id == account_id:
            return account
    raise HTTPException(status_code=404, detail="Account not found")


@router.get("/api/clients")
def clients_index(_auth: None = Depends(require_api_key)):
    clients = DataHandler.load_clients()
    return {"clients": list_clients(clients)}


@router.get("/api/clients/{client_id}")
def client_view(client_id: str, _auth: None = Depends(require_api_key)):
    clients = DataHandler.load_clients()
    client = _find_client(clients, client_id)
    return client_detail(client)


@router.post("/api/clients")
def client_create(payload: ClientPayload, _auth: None = Depends(require_api_key)):
    clients = DataHandler.load_clients()
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Client name required")
    risk_profile = payload.risk_profile.strip() if payload.risk_profile else ""
    tax_profile = payload.tax_profile or {}
    client = Client(
        name=name,
        risk_profile=risk_profile or "Not Assessed",
        risk_profile_source="manual" if risk_profile else "auto",
        tax_profile={
            "residency_country": tax_profile.get("residency_country", ""),
            "tax_country": tax_profile.get("tax_country", ""),
            "reporting_currency": tax_profile.get("reporting_currency", "USD"),
            "treaty_country": tax_profile.get("treaty_country", ""),
            "tax_id": tax_profile.get("tax_id", ""),
        },
        accounts=[],
    )
    clients.append(client)
    DataHandler.save_clients(clients)
    return client_detail(client)


@router.patch("/api/clients/{client_id}")
def client_update(
    client_id: str,
    payload: ClientUpdatePayload,
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    client = _find_client(clients, client_id)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Client name required")
        client.name = name
    if payload.risk_profile is not None:
        cleaned = payload.risk_profile.strip()
        if cleaned:
            client.risk_profile = cleaned
            client.risk_profile_source = "manual"
        else:
            client.risk_profile = "Not Assessed"
            client.risk_profile_source = "auto"
    if payload.tax_profile is not None:
        profile = client.tax_profile or {}
        for key, value in payload.tax_profile.items():
            profile[key] = value
        client.tax_profile = profile
    DataHandler.save_clients(clients)
    return client_detail(client)


@router.get("/api/clients/{client_id}/dashboard")
def client_dashboard_view(
    client_id: str,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    for client in clients:
        if client.client_id == client_id:
            return portfolio_dashboard(client, interval=interval)
    raise HTTPException(status_code=404, detail="Client not found")


@router.post("/api/clients/{client_id}/accounts")
def account_create(
    client_id: str,
    payload: AccountPayload,
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    client = _find_client(clients, client_id)
    name = payload.account_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Account name required")
    account = Account(
        account_name=name,
        account_type=payload.account_type or "Taxable",
        ownership_type=payload.ownership_type or "Individual",
        custodian=payload.custodian or "",
        tags=payload.tags or [],
        tax_settings=payload.tax_settings or {
            "jurisdiction": "",
            "account_currency": "USD",
            "withholding_rate": None,
            "tax_exempt": False,
        },
    )
    client.accounts.append(account)
    DataHandler.save_clients(clients)
    return {"client": client_detail(client), "account": account_detail(account)}


@router.patch("/api/clients/{client_id}/accounts/{account_id}")
def account_update(
    client_id: str,
    account_id: str,
    payload: AccountUpdatePayload,
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    client = _find_client(clients, client_id)
    account = _find_account(client, account_id)
    if payload.account_name is not None:
        name = payload.account_name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Account name required")
        account.account_name = name
    if payload.account_type is not None:
        account.account_type = payload.account_type
    if payload.ownership_type is not None:
        account.ownership_type = payload.ownership_type
    if payload.custodian is not None:
        account.custodian = payload.custodian
    if payload.tags is not None:
        account.tags = payload.tags
    if payload.tax_settings is not None:
        settings = account.tax_settings or {}
        for key, value in payload.tax_settings.items():
            settings[key] = value
        account.tax_settings = settings
    DataHandler.save_clients(clients)
    return {"client": client_detail(client), "account": account_detail(account)}


@router.get("/api/clients/{client_id}/accounts/{account_id}/dashboard")
def account_dashboard_view(
    client_id: str,
    account_id: str,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    for client in clients:
        if client.client_id == client_id:
            for account in client.accounts:
                if account.account_id == account_id:
                    return account_dashboard(client, account, interval=interval)
            raise HTTPException(status_code=404, detail="Account not found")
    raise HTTPException(status_code=404, detail="Client not found")


@router.get("/api/clients/{client_id}/patterns")
def client_patterns_view(
    client_id: str,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    for client in clients:
        if client.client_id == client_id:
            return client_patterns(client, interval=interval)
    raise HTTPException(status_code=404, detail="Client not found")


@router.get("/api/clients/{client_id}/accounts/{account_id}/patterns")
def account_patterns_view(
    client_id: str,
    account_id: str,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    for client in clients:
        if client.client_id == client_id:
            for account in client.accounts:
                if account.account_id == account_id:
                    return account_patterns(client, account, interval=interval)
            raise HTTPException(status_code=404, detail="Account not found")
    raise HTTPException(status_code=404, detail="Client not found")
