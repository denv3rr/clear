from __future__ import annotations

from fastapi import APIRouter, Depends

from web_api.diagnostics import (
    client_counts,
    feed_status,
    news_cache_info,
    report_cache_info,
    system_snapshot,
    tracker_status,
)
from web_api.auth import require_api_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


@router.get("/api/tools/diagnostics")
def diagnostics(_auth: None = Depends(require_api_key)):
    system = system_snapshot()
    payload = {
        "system": system.get("system"),
        "metrics": system.get("metrics"),
        "feeds": feed_status(),
        "trackers": tracker_status(),
        "intel": {
            "news_cache": news_cache_info(),
        },
        "clients": client_counts(),
        "reports": report_cache_info(),
    }
    warnings = validate_payload(
        payload,
        required_keys=("system", "metrics", "feeds", "trackers", "intel", "clients", "reports"),
        warnings=[],
    )
    if payload["trackers"].get("count", 0) == 0:
        warnings.append("Diagnostics: no tracker signals.")
    if payload["intel"]["news_cache"].get("status") == "stale":
        warnings.append("Diagnostics: news cache stale.")
    return attach_meta(
        payload,
        route="/api/tools/diagnostics",
        source="diagnostics",
        warnings=warnings,
    )
