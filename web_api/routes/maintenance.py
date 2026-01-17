from __future__ import annotations

import json
import os
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from modules.client_mgr.data_handler import DataHandler
from core import models
from core.database import SessionLocal
from modules.client_store import bootstrap_clients_from_json
from web_api.auth import require_api_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


class MaintenanceConfirmPayload(BaseModel):
    confirm: bool = False


@router.post("/api/maintenance/normalize-lots")
def normalize_lot_timestamps(
    payload: MaintenanceConfirmPayload = Body(default_factory=MaintenanceConfirmPayload),
    _auth: None = Depends(require_api_key),
):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required.")
    bootstrap_clients_from_json()
    path = DataHandler.CLIENT_FILE
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="clients.json not found")
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        payload, migrated = DataHandler._migrate_clients_payload(payload)
        if not migrated:
            result = {"normalized": False, "message": "No legacy timestamps found."}
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
            result = {"normalized": True, "message": "Lot timestamps normalized."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Normalization failed: {exc}")
    warnings = validate_payload(result, required_keys=("normalized", "message"), warnings=[])
    return attach_meta(
        result,
        route="/api/maintenance/normalize-lots",
        source="maintenance",
        warnings=warnings,
    )


@router.post("/api/maintenance/clear-report-cache")
def clear_report_cache(
    payload: MaintenanceConfirmPayload = Body(default_factory=MaintenanceConfirmPayload),
    _auth: None = Depends(require_api_key),
):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required.")
    path = os.path.join("data", "ai_report_cache.json")
    removed = False
    if os.path.exists(path):
        os.remove(path)
        removed = True
    result: Dict[str, Any] = {"cleared": removed, "path": path}
    warnings = validate_payload(result, required_keys=("cleared", "path"), warnings=[])
    return attach_meta(
        result,
        route="/api/maintenance/clear-report-cache",
        source="maintenance",
        warnings=warnings,
    )


@router.post("/api/maintenance/cleanup-orphans")
def cleanup_orphans(
    payload: MaintenanceConfirmPayload = Body(default_factory=MaintenanceConfirmPayload),
    _auth: None = Depends(require_api_key),
):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required.")
    db = SessionLocal()
    try:
        account_ids = {row[0] for row in db.query(models.Account.id).all()}
        holding_ids = {row[0] for row in db.query(models.Holding.id).all()}
        holdings_query = db.query(models.Holding)
        if account_ids:
            holdings_query = holdings_query.filter(
                ~models.Holding.account_id.in_(account_ids)
            )
        lots_query = db.query(models.Lot)
        if holding_ids:
            lots_query = lots_query.filter(~models.Lot.holding_id.in_(holding_ids))
        orphan_lots = lots_query.all()
        orphan_holdings = holdings_query.all()
        for lot in orphan_lots:
            db.delete(lot)
        for holding in orphan_holdings:
            db.delete(holding)
        db.commit()
        result = {
            "removed_holdings": len(orphan_holdings),
            "removed_lots": len(orphan_lots),
        }
    finally:
        db.close()
    warnings = validate_payload(
        result,
        required_keys=("removed_holdings", "removed_lots"),
        warnings=[],
    )
    return attach_meta(
        result,
        route="/api/maintenance/cleanup-orphans",
        source="maintenance",
        warnings=warnings,
    )
