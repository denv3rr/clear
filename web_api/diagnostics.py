from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

from modules.client_mgr.data_handler import DataHandler
from core.database import SessionLocal
from core import models
from modules.client_store import DbClientStore
from modules.market_data.trackers import GlobalTrackers
from utils.system import SystemHost


def feed_status() -> Dict[str, object]:
    flight_urls = [item.strip() for item in os.getenv("FLIGHT_DATA_URL", "").split(",") if item.strip()]
    flight_paths = [item.strip() for item in os.getenv("FLIGHT_DATA_PATH", "").split(",") if item.strip()]
    shipping_url = os.getenv("SHIPPING_DATA_URL")
    opensky_basic = bool(os.getenv("OPENSKY_USERNAME") and os.getenv("OPENSKY_PASSWORD"))
    opensky_oauth = bool(os.getenv("OPENSKY_CLIENT_ID") and os.getenv("OPENSKY_CLIENT_SECRET"))
    opensky_creds = opensky_basic or opensky_oauth
    auth_mode = "anonymous"
    if opensky_oauth:
        auth_mode = "oauth"
    elif opensky_basic:
        auth_mode = "basic"
    return {
        "flights": {
            "url_sources": len(flight_urls),
            "path_sources": len(flight_paths),
            "configured": bool(flight_urls or flight_paths or opensky_creds),
        },
        "shipping": {
            "configured": bool(shipping_url),
        },
        "opensky": {
            "credentials_set": opensky_creds,
            "auth_mode": auth_mode,
            "basic_credentials": opensky_basic,
            "oauth_credentials": opensky_oauth,
        },
    }


def system_snapshot() -> Dict[str, object]:
    return {
        "system": SystemHost.get_info(),
        "metrics": SystemHost.get_metrics(os.getcwd()),
    }


def tracker_status() -> Dict[str, object]:
    trackers = GlobalTrackers()
    snapshot = trackers.get_snapshot(mode="combined", allow_refresh=False)
    warnings = snapshot.get("warnings") or []
    return {
        "count": int(snapshot.get("count", 0) or 0),
        "warnings": warnings,
        "warning_count": len(warnings),
    }


def client_counts() -> Dict[str, int]:
    store = DbClientStore()
    clients = store.fetch_all_clients()
    account_count = 0
    holdings_count = 0
    lots_count = 0
    for client in clients:
        accounts = client.get("accounts", []) or []
        account_count += len(accounts)
        for account in accounts:
            holdings = account.get("holdings", {}) or {}
            manual = account.get("manual_holdings", []) or []
            lots = account.get("lots", {}) or {}
            holdings_count += len(holdings) + len(manual)
            for lot_list in lots.values():
                lots_count += len(lot_list or [])
    return {
        "clients": len(clients),
        "accounts": account_count,
        "holdings": holdings_count,
        "lots": lots_count,
    }


def duplicate_account_summary() -> Dict[str, object]:
    store = DbClientStore()
    return store.find_duplicate_accounts()


def orphaned_counts() -> Dict[str, int]:
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
        return {
            "holdings": int(holdings_query.count()),
            "lots": int(lots_query.count()),
        }
    finally:
        db.close()


def news_cache_info(max_age_hours: int = 6) -> Dict[str, Optional[object]]:
    path = os.path.join("data", "intel_news.json")
    if not os.path.exists(path):
        return {"status": "missing", "items": 0, "age_hours": None}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        ts = int(payload.get("ts", 0) or 0)
        items = payload.get("items") or []
        age_hours = round(max(0.0, (time.time() - ts) / 3600.0), 2) if ts else None
        status = "fresh"
        if not items:
            status = "empty"
        elif age_hours is not None and age_hours > max_age_hours:
            status = "stale"
        return {"status": status, "items": len(items), "age_hours": age_hours}
    except Exception:
        return {"status": "error", "items": 0, "age_hours": None}


def report_cache_info() -> Dict[str, Optional[object]]:
    path = os.path.join("data", "ai_report_cache.json")
    if not os.path.exists(path):
        return {"status": "missing", "items": 0}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            count = len(payload)
        elif isinstance(payload, dict):
            count = len(payload.keys())
        else:
            count = 0
        return {"status": "ready", "items": count}
    except Exception:
        return {"status": "error", "items": 0}
