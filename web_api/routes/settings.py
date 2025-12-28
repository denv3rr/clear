from __future__ import annotations

import json
import os
from typing import Dict

from fastapi import APIRouter, Depends

from web_api.auth import require_api_key

router = APIRouter()


def _load_settings_payload() -> Dict[str, object]:
    path = os.path.join("config", "settings.json")
    if not os.path.exists(path):
        return {"settings": {}, "error": "settings.json not found"}
    try:
        with open(path, "r", encoding="ascii") as handle:
            data = handle.read()
        return {"settings": json.loads(data), "error": None}
    except Exception as exc:
        return {"settings": {}, "error": f"Invalid settings.json ({exc})"}


def _redact_settings(settings: Dict[str, object]) -> Dict[str, object]:
    cleaned = dict(settings)
    credentials = settings.get("credentials") if isinstance(settings, dict) else {}
    if not isinstance(credentials, dict):
        credentials = {}
    cleaned["credentials"] = {
        "finnhub_key_set": bool(credentials.get("finnhub_key")),
        "smtp_configured": bool(credentials.get("smtp")),
    }
    return cleaned


def _feed_status() -> Dict[str, object]:
    flight_urls = [item.strip() for item in os.getenv("FLIGHT_DATA_URL", "").split(",") if item.strip()]
    flight_paths = [item.strip() for item in os.getenv("FLIGHT_DATA_PATH", "").split(",") if item.strip()]
    shipping_url = os.getenv("SHIPPING_DATA_URL")
    return {
        "flights": {
            "url_sources": len(flight_urls),
            "path_sources": len(flight_paths),
            "configured": bool(flight_urls or flight_paths),
        },
        "shipping": {
            "configured": bool(shipping_url),
        },
        "opensky": {
            "credentials_set": bool(os.getenv("OPENSKY_USERNAME") and os.getenv("OPENSKY_PASSWORD")),
        },
    }


@router.get("/api/settings")
def settings_view(_auth: None = Depends(require_api_key)):
    payload = _load_settings_payload()
    return {
        "settings": _redact_settings(payload.get("settings", {})),
        "error": payload.get("error"),
        "feeds": _feed_status(),
    }
