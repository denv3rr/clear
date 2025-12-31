from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core import models
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
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


def _find_client(db: Session, client_id: int) -> models.Client:
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


def _find_account(db: Session, client_id: int, account_id: int) -> models.Account:
    account = db.query(models.Account).filter(models.Account.id == account_id, models.Account.client_id == client_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("/api/clients")
def clients_index(_auth: None = Depends(require_api_key), db: Session = Depends(get_db)):
    clients = db.query(models.Client).all()
    payload = {"clients": list_clients(clients)}
    warnings = validate_payload(payload, required_keys=("clients",), warnings=[])
    if not payload["clients"]:
        warnings.append("No clients available.")
    return attach_meta(
        payload,
        route="/api/clients",
        source="database",
        warnings=warnings,
    )


@router.get("/api/clients/{client_id}")
def client_view(client_id: int, _auth: None = Depends(require_api_key), db: Session = Depends(get_db)):
    client = _find_client(db, client_id)
    payload = client_detail(client)
    warnings = validate_payload(payload, required_keys=("client_id", "accounts"), warnings=[])
    if not payload.get("accounts"):
        warnings.append("Client has no accounts.")
    return attach_meta(
        payload,
        route="/api/clients/{client_id}",
        source="database",
        warnings=warnings,
    )


@router.post("/api/clients")
def client_create(payload: ClientPayload, _auth: None = Depends(require_api_key), db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Client name required")
    
    risk_profile = payload.risk_profile.strip() if payload.risk_profile else ""
    
    client = models.Client(
        name=name,
        risk_profile=risk_profile or "Not Assessed",
    )
    db.add(client)
    db.commit()
    response = client_detail(client)
    warnings = validate_payload(response, required_keys=("client_id",), warnings=[])
    return attach_meta(
        response,
        route="/api/clients",
        source="database",
        warnings=warnings,
    )


@router.patch("/api/clients/{client_id}")
def client_update(
    client_id: int,
    payload: ClientUpdatePayload,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    client = _find_client(db, client_id)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Client name required")
        client.name = name
    if payload.risk_profile is not None:
        cleaned = payload.risk_profile.strip()
        if cleaned:
            client.risk_profile = cleaned
        else:
            client.risk_profile = "Not Assessed"
    db.commit()
    db.refresh(client)
    response = client_detail(client)
    warnings = validate_payload(response, required_keys=("client_id",), warnings=[])
    return attach_meta(
        response,
        route="/api/clients/{client_id}",
        source="database",
        warnings=warnings,
    )


@router.get("/api/clients/{client_id}/dashboard")
def client_dashboard_view(
    client_id: int,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    client = _find_client(db, client_id)
    payload = portfolio_dashboard(client, interval=interval)
    warnings = list(payload.get("warnings", []) or [])
    warnings = validate_payload(
        payload,
        required_keys=("client", "interval", "totals", "holdings", "history"),
        warnings=warnings,
    )
    if not payload.get("holdings"):
        warnings.append("Client dashboard has no holdings.")
    return attach_meta(
        payload,
        route="/api/clients/{client_id}/dashboard",
        source="database",
        warnings=warnings,
    )


@router.post("/api/clients/{client_id}/accounts")
def account_create(
    client_id: int,
    payload: AccountPayload,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    client = _find_client(db, client_id)
    name = payload.account_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Account name required")
    account = models.Account(
        name=name,
        account_type=payload.account_type or "Taxable",
        client_id=client.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    payload = {"client": client_detail(client), "account": account_detail(account)}
    warnings = validate_payload(payload, required_keys=("client", "account"), warnings=[])
    return attach_meta(
        payload,
        route="/api/clients/{client_id}/accounts",
        source="database",
        warnings=warnings,
    )


@router.patch("/api/clients/{client_id}/accounts/{account_id}")
def account_update(
    client_id: int,
    account_id: int,
    payload: AccountUpdatePayload,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    client = _find_client(db, client_id)
    account = _find_account(db, client_id, account_id)
    if payload.account_name is not None:
        name = payload.account_name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Account name required")
        account.name = name
    if payload.account_type is not None:
        account.account_type = payload.account_type
    db.commit()
    db.refresh(account)
    payload = {"client": client_detail(client), "account": account_detail(account)}
    warnings = validate_payload(payload, required_keys=("client", "account"), warnings=[])
    return attach_meta(
        payload,
        route="/api/clients/{client_id}/accounts/{account_id}",
        source="database",
        warnings=warnings,
    )


@router.get("/api/clients/{client_id}/accounts/{account_id}/dashboard")
def account_dashboard_view(
    client_id: int,
    account_id: int,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    client = _find_client(db, client_id)
    account = _find_account(db, client_id, account_id)
    payload = account_dashboard(client, account, interval=interval)
    warnings = list(payload.get("warnings", []) or [])
    warnings = validate_payload(
        payload,
        required_keys=("client", "account", "interval", "totals", "holdings", "history"),
        warnings=warnings,
    )
    if not payload.get("holdings"):
        warnings.append("Account dashboard has no holdings.")
    return attach_meta(
        payload,
        route="/api/clients/{client_id}/accounts/{account_id}/dashboard",
        source="database",
        warnings=warnings,
    )


@router.get("/api/clients/{client_id}/patterns")
def client_patterns_view(
    client_id: int,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    client = _find_client(db, client_id)
    payload = client_patterns(client, interval=interval)
    warnings = validate_payload(
        payload,
        required_keys=("interval", "scope", "label"),
        warnings=[],
    )
    if payload.get("error"):
        warnings.append("Client patterns returned error.")
    return attach_meta(
        payload,
        route="/api/clients/{client_id}/patterns",
        source="database",
        warnings=warnings,
    )


@router.get("/api/clients/{client_id}/accounts/{account_id}/patterns")
def account_patterns_view(
    client_id: int,
    account_id: int,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    client = _find_client(db, client_id)
    account = _find_account(db, client_id, account_id)
    payload = account_patterns(client, account, interval=interval)
    warnings = validate_payload(
        payload,
        required_keys=("interval", "scope", "label"),
        warnings=[],
    )
    if payload.get("error"):
        warnings.append("Account patterns returned error.")
    return attach_meta(
        payload,
        route="/api/clients/{client_id}/accounts/{account_id}/patterns",
        source="database",
        warnings=warnings,
    )