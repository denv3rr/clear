from __future__ import annotations

from fastapi import APIRouter, Depends

from web_api.diagnostics import (
    client_counts,
    duplicate_client_summary,
    duplicate_account_summary,
    feed_status,
    news_cache_info,
    orphaned_counts,
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
    news_cache = news_cache_info()
    payload = {
        "system": system.get("system"),
        "metrics": system.get("metrics"),
        "feeds": feed_status(),
        "trackers": tracker_status(),
        "intel": {
            "news_cache": news_cache,
        },
        "clients": client_counts(),
        "duplicates": {
            "accounts": duplicate_account_summary(),
            "client_names": duplicate_client_summary(),
            "news": {"count": int(news_cache.get("duplicate_items", 0) or 0)},
        },
        "orphans": orphaned_counts(),
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
    if payload["duplicates"]["news"].get("count", 0) > 0:
        warnings.append("Diagnostics: duplicate news entries detected in the raw cache.")
    return attach_meta(
        payload,
        route="/api/tools/diagnostics",
        source="diagnostics",
        warnings=warnings,
    )
