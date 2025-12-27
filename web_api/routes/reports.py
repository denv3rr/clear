from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from modules.client_mgr.data_handler import DataHandler
from modules.reporting.engine import ReportEngine
from web_api.auth import require_api_key

router = APIRouter()


@router.get("/api/reports/client/{client_id}")
def client_report(
    client_id: str,
    detail: bool = Query(False),
    fmt: str = Query("md", pattern="^(md|json|terminal)$"),
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    for client in clients:
        if client.client_id == client_id:
            engine = ReportEngine()
            report = engine.generate_client_portfolio_report(client, output_format=fmt, detailed=detail)
            return {"format": fmt, "content": report.content, "payload": report.payload.__dict__}
    raise HTTPException(status_code=404, detail="Client not found")


@router.get("/api/reports/client/{client_id}/accounts/{account_id}")
def account_report(
    client_id: str,
    account_id: str,
    fmt: str = Query("md", pattern="^(md|json|terminal)$"),
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    for client in clients:
        if client.client_id == client_id:
            for account in client.accounts:
                if account.account_id == account_id:
                    engine = ReportEngine()
                    report = engine.generate_account_portfolio_report(client, account, output_format=fmt)
                    return {"format": fmt, "content": report.content, "payload": report.payload.__dict__}
            raise HTTPException(status_code=404, detail="Account not found")
    raise HTTPException(status_code=404, detail="Client not found")
