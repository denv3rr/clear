from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from modules.client_mgr.data_handler import DataHandler
from modules.view_models import (
    account_dashboard,
    account_patterns,
    client_detail,
    client_patterns,
    list_clients,
    portfolio_dashboard,
)
from web_api.auth import require_api_key

router = APIRouter()


@router.get("/api/clients")
def clients_index(_auth: None = Depends(require_api_key)):
    clients = DataHandler.load_clients()
    return {"clients": list_clients(clients)}


@router.get("/api/clients/{client_id}")
def client_view(client_id: str, _auth: None = Depends(require_api_key)):
    clients = DataHandler.load_clients()
    for client in clients:
        if client.client_id == client_id:
            return client_detail(client)
    raise HTTPException(status_code=404, detail="Client not found")


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
