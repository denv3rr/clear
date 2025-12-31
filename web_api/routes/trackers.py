from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from modules.market_data.trackers import GlobalTrackers
from web_api.auth import require_api_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


@router.get("/api/trackers/snapshot")
def tracker_snapshot(
    mode: str = Query("combined", pattern="^(combined|flights|ships)$"),
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    payload = trackers.get_snapshot(mode=mode)
    warnings = list(payload.get("warnings", []) or [])
    if payload.get("count", 0) == 0:
        warnings.append("No tracker points returned.")
    warnings = validate_payload(
        payload,
        required_keys=("mode", "count", "points"),
        non_empty_keys=("points",),
        warnings=warnings,
    )
    return attach_meta(
        payload,
        route="/api/trackers/snapshot",
        source="trackers",
        warnings=warnings,
    )


@router.get("/api/trackers/search")
def tracker_search(
    q: str = Query(..., min_length=1),
    mode: str = Query("combined", pattern="^(combined|flights|ships)$"),
    fields: Optional[str] = Query(None),
    kind: Optional[str] = Query(None, pattern="^(flight|ship)$"),
    limit: int = Query(50, ge=1, le=200),
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    snapshot = trackers.get_snapshot(mode=mode)
    field_list = [item.strip() for item in (fields or "").split(",") if item.strip()] or None
    payload = trackers.search_snapshot(snapshot, query=q, fields=field_list, kind=kind, limit=limit)
    warnings = validate_payload(
        payload,
        required_keys=("query", "count", "points"),
        warnings=[],
    )
    if payload.get("count", 0) == 0:
        warnings.append("No tracker matches found.")
    return attach_meta(
        payload,
        route="/api/trackers/search",
        source="trackers",
        warnings=warnings,
    )


@router.get("/api/trackers/history/{tracker_id}")
def tracker_history(
    tracker_id: str,
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    payload = trackers.get_history(tracker_id)
    warnings = validate_payload(
        payload if isinstance(payload, dict) else {},
        required_keys=("id", "history"),
        warnings=[],
    )
    if isinstance(payload, dict) and not payload.get("history"):
        warnings.append("No tracker history available.")
    return attach_meta(
        payload if isinstance(payload, dict) else {"history": [], "meta": {}},
        route="/api/trackers/history",
        source="trackers",
        warnings=warnings,
    )


@router.get("/api/trackers/detail/{tracker_id}")
def tracker_detail(
    tracker_id: str,
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    payload = trackers.get_detail(tracker_id, allow_refresh=False)
    warnings = validate_payload(
        payload if isinstance(payload, dict) else {},
        required_keys=("id", "point", "history", "summary"),
        warnings=[],
    )
    if isinstance(payload, dict) and not payload.get("point"):
        warnings.append("Tracker detail unavailable.")
    return attach_meta(
        payload if isinstance(payload, dict) else {"point": None, "meta": {}},
        route="/api/trackers/detail",
        source="trackers",
        warnings=warnings,
    )
