from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from modules.market_data.trackers import GlobalTrackers
from web_api.auth import require_api_key

router = APIRouter()


@router.get("/api/trackers/snapshot")
def tracker_snapshot(
    mode: str = Query("combined", pattern="^(combined|flights|ships)$"),
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    return trackers.get_snapshot(mode=mode)


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
    return trackers.search_snapshot(snapshot, query=q, fields=field_list, kind=kind, limit=limit)


@router.get("/api/trackers/history/{tracker_id}")
def tracker_history(
    tracker_id: str,
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    return trackers.get_history(tracker_id)


@router.get("/api/trackers/detail/{tracker_id}")
def tracker_detail(
    tracker_id: str,
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    return trackers.get_detail(tracker_id, allow_refresh=False)
