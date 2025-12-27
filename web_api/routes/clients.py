from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from modules.client_mgr.data_handler import DataHandler
from modules.view_models import client_detail, list_clients
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
