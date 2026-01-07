from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.database import SessionLocal
from modules.view_models import (
    account_dashboard,
    account_detail,
    account_patterns,
    client_detail,
    client_patterns,
    list_clients,
    portfolio_dashboard,
)
from modules.client_store import DbClientStore
from modules.client_mgr.schema import Client, Account
from web_api.auth import require_api_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DuplicateCleanupPayload(BaseModel):
    confirm: bool = False


def _find_account_payload(client_payload: Dict[str, Any], account_ref: Any) -> Optional[Dict[str, Any]]:
    ref = str(account_ref)
    for account in client_payload.get("accounts", []) or []:
        if str(account.get("account_id")) == ref:
            return account
    return None


@router.get("/api/clients")
def clients_index(_auth: None = Depends(require_api_key), db: Session = Depends(get_db)):
    store = DbClientStore(db)
    clients = store.fetch_all_clients()
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


@router.get("/api/clients/duplicates")
def client_duplicate_accounts(
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    store = DbClientStore(db)
    payload = store.find_duplicate_accounts()
    warnings = validate_payload(
        payload,
        required_keys=("count", "clients", "details"),
        warnings=[],
    )
    if payload.get("count", 0) > 0:
        warnings.append("Duplicate accounts detected.")
    return attach_meta(
        payload,
        route="/api/clients/duplicates",
        source="database",
        warnings=warnings,
    )


@router.post("/api/clients/duplicates/cleanup")
def cleanup_client_duplicates(
    payload: DuplicateCleanupPayload,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Cleanup requires confirm=true.")
    store = DbClientStore(db)
    result = store.remove_duplicate_accounts()
    warnings = validate_payload(
        result,
        required_keys=("removed", "clients", "remaining"),
        warnings=[],
    )
    remaining = result.get("remaining", {}) if isinstance(result, dict) else {}
    remaining_count = int(remaining.get("count", 0) or 0)
    if remaining_count > 0:
        warnings.append("Duplicate accounts still remain after cleanup.")
    return attach_meta(
        result,
        route="/api/clients/duplicates/cleanup",
        source="database",
        warnings=warnings,
    )


@router.get("/api/clients/{client_id}")
def client_view(client_id: str, _auth: None = Depends(require_api_key), db: Session = Depends(get_db)):
    store = DbClientStore(db)
    client_payload = store.fetch_client(client_id)
    if client_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    payload = client_detail(client_payload)
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
def client_create(payload: Client, _auth: None = Depends(require_api_key), db: Session = Depends(get_db)):
    store = DbClientStore(db)
    try:
        response = store.create_client(payload.model_dump())
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Client name already exists.")
    response = client_detail(response)
    warnings = validate_payload(response, required_keys=("client_id",), warnings=[])
    return attach_meta(
        response,
        route="/api/clients",
        source="database",
        warnings=warnings,
    )


@router.patch("/api/clients/{client_id}")
def client_update(
    client_id: str,
    payload: Client,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    store = DbClientStore(db)
    updated = store.update_client(client_id, payload.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="Client not found")
    response = client_detail(updated)
    warnings = validate_payload(response, required_keys=("client_id",), warnings=[])
    return attach_meta(
        response,
        route="/api/clients/{client_id}",
        source="database",
        warnings=warnings,
    )


@router.get("/api/clients/{client_id}/dashboard")
def client_dashboard_view(
    client_id: str,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    store = DbClientStore(db)
    client_payload = store.fetch_client(client_id)
    if client_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    payload = portfolio_dashboard(client_payload, interval=interval)
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
    client_id: str,
    payload: Account,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    store = DbClientStore(db)
    account_payload = store.create_account(client_id, payload.model_dump())
    if account_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    client_payload = store.fetch_client(client_id)
    if client_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    payload = {"client": client_detail(client_payload), "account": account_detail(account_payload)}
    warnings = validate_payload(payload, required_keys=("client", "account"), warnings=[])
    return attach_meta(
        payload,
        route="/api/clients/{client_id}/accounts",
        source="database",
        warnings=warnings,
    )


@router.patch("/api/clients/{client_id}/accounts/{account_id}")
def account_update(
    client_id: str,
    account_id: str,
    payload: Account,
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    store = DbClientStore(db)
    account_payload = store.update_account(client_id, account_id, payload.model_dump())
    if account_payload is None:
        raise HTTPException(status_code=404, detail="Account not found")
    client_payload = store.fetch_client(client_id)
    if client_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    payload = {"client": client_detail(client_payload), "account": account_detail(account_payload)}
    warnings = validate_payload(payload, required_keys=("client", "account"), warnings=[])
    return attach_meta(
        payload,
        route="/api/clients/{client_id}/accounts/{account_id}",
        source="database",
        warnings=warnings,
    )


@router.get("/api/clients/{client_id}/accounts/{account_id}/dashboard")
def account_dashboard_view(
    client_id: str,
    account_id: str,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    store = DbClientStore(db)
    client_payload = store.fetch_client(client_id)
    if client_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    account_payload = _find_account_payload(client_payload, account_id)
    if account_payload is None:
        raise HTTPException(status_code=404, detail="Account not found")
    payload = account_dashboard(client_payload, account_payload, interval=interval)
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
    client_id: str,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    store = DbClientStore(db)
    client_payload = store.fetch_client(client_id)
    if client_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    payload = client_patterns(client_payload, interval=interval)
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
    client_id: str,
    account_id: str,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    _auth: None = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    store = DbClientStore(db)
    client_payload = store.fetch_client(client_id)
    if client_payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    account_payload = _find_account_payload(client_payload, account_id)
    if account_payload is None:
        raise HTTPException(status_code=404, detail="Account not found")
    payload = account_patterns(client_payload, account_payload, interval=interval)
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
