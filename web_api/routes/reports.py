from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from modules.client_mgr.data_handler import DataHandler
from modules.reporting.engine import ReportEngine
from web_api.auth import require_api_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


@router.get("/api/reports/client/{client_id}")
def client_report(
    client_id: str,
    detail: bool = Query(False),
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    fmt: str = Query("md", pattern="^(md|json|terminal)$"),
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    for client in clients:
        if client.client_id == client_id:
            engine = ReportEngine()
            report = engine.generate_client_portfolio_report(
                client,
                output_format=fmt,
                interval=interval,
                detailed=detail,
            )
            payload = report.payload.__dict__ if report.payload else {}
            response = {"format": fmt, "content": report.content, "payload": payload}
            warnings = validate_payload(
                response,
                required_keys=("format", "content", "payload"),
                non_empty_keys=("content",),
            )
            return attach_meta(
                response,
                route="/api/reports/client/{client_id}",
                source="report_engine",
                warnings=warnings,
            )
    raise HTTPException(status_code=404, detail="Client not found")


@router.get("/api/reports/client/{client_id}/accounts/{account_id}")
def account_report(
    client_id: str,
    account_id: str,
    interval: str = Query("1M", pattern="^(1W|1M|3M|6M|1Y)$"),
    fmt: str = Query("md", pattern="^(md|json|terminal)$"),
    _auth: None = Depends(require_api_key),
):
    clients = DataHandler.load_clients()
    for client in clients:
        if client.client_id == client_id:
            for account in client.accounts:
                if account.account_id == account_id:
                    engine = ReportEngine()
                    report = engine.generate_account_portfolio_report(
                        client,
                        account,
                        output_format=fmt,
                        interval=interval,
                    )
                    payload = report.payload.__dict__ if report.payload else {}
                    response = {"format": fmt, "content": report.content, "payload": payload}
                    warnings = validate_payload(
                        response,
                        required_keys=("format", "content", "payload"),
                        non_empty_keys=("content",),
                    )
                    return attach_meta(
                        response,
                        route="/api/reports/client/{client_id}/accounts/{account_id}",
                        source="report_engine",
                        warnings=warnings,
                    )
            raise HTTPException(status_code=404, detail="Account not found")
    raise HTTPException(status_code=404, detail="Client not found")
