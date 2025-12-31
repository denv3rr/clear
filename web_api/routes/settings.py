from __future__ import annotations

import json
import os
from typing import Dict

from fastapi import APIRouter, Depends

from web_api.auth import require_api_key
from web_api.diagnostics import feed_status, system_snapshot
from web_api.view_model import attach_meta, validate_payload

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
        "finnhub_key_set": bool(credentials.get("finnhub_key") or os.getenv("FINNHUB_API_KEY")),
        "smtp_configured": bool(credentials.get("smtp")),
    }
    return cleaned


@router.get("/api/settings")
def settings_view(_auth: None = Depends(require_api_key)):
    payload = _load_settings_payload()
    system = system_snapshot()
    response = {
        "settings": _redact_settings(payload.get("settings", {})),
        "error": payload.get("error"),
        "feeds": feed_status(),
        "system": system.get("system"),
        "system_metrics": system.get("metrics"),
    }
    warnings = validate_payload(
        response,
        required_keys=("settings", "feeds", "system", "system_metrics"),
        warnings=[],
    )
    if payload.get("error"):
        warnings.append("Settings payload error.")
    return attach_meta(
        response,
        route="/api/settings",
        source="settings",
        warnings=warnings,
        status="error" if warnings else "ok",
    )
