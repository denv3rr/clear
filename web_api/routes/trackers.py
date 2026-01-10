from __future__ import annotations

from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from modules.market_data.trackers import GlobalTrackers
from web_api.auth import require_api_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()

class GeofenceRequest(BaseModel):
    id: Optional[str] = None
    label: Optional[str] = None
    lat: float
    lon: float
    radius_km: float = Field(..., gt=0)


class TrackerAnalysisRequest(BaseModel):
    tracker_id: str
    window_sec: int = Field(3600, gt=0)
    loiter_radius_km: float = Field(10.0, gt=0)
    loiter_min_minutes: float = Field(20.0, gt=0)
    geofences: list[GeofenceRequest] = Field(default_factory=list)

def _parse_bbox(value: Optional[str]) -> Optional[Tuple[float, float, float, float]]:
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise HTTPException(
            status_code=400,
            detail="bbox must be min_lat,min_lon,max_lat,max_lon",
        )
    try:
        min_lat, min_lon, max_lat, max_lon = (float(part) for part in parts)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="bbox must contain numeric values",
        ) from exc
    if min_lat > max_lat or min_lon > max_lon:
        raise HTTPException(
            status_code=400,
            detail="bbox min values must be <= max values",
        )
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise HTTPException(
            status_code=400,
            detail="bbox latitude must be within [-90, 90]",
        )
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        raise HTTPException(
            status_code=400,
            detail="bbox longitude must be within [-180, 180]",
        )
    return (min_lat, min_lon, max_lat, max_lon)


@router.get("/api/trackers/snapshot")
def tracker_snapshot(
    mode: str = Query("combined", pattern="^(combined|flights|ships)$"),
    category: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    operator: Optional[str] = Query(None),
    bbox: Optional[str] = Query(None),
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    bbox_tuple = _parse_bbox(bbox)
    payload = trackers.get_snapshot(mode=mode)
    base_count = payload.get("count", 0)
    payload = trackers.apply_filters(
        payload,
        category=category,
        country=country,
        operator=operator,
        bbox=bbox_tuple,
    )
    warnings = list(payload.get("warnings", []) or [])
    filtered = any(item for item in (category, country, operator, bbox_tuple))
    if base_count == 0:
        warnings.append("No tracker points returned.")
    elif filtered and payload.get("count", 0) == 0:
        warnings.append("No tracker points match filters.")
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


@router.get("/api/trackers/analysis/{tracker_id}")
def tracker_analysis(
    tracker_id: str,
    window_sec: int = Query(3600, ge=60, le=86400),
    loiter_radius_km: float = Query(10.0, gt=0),
    loiter_min_minutes: float = Query(20.0, gt=0),
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    payload = trackers.analyze_tracker(
        tracker_id,
        window_sec=window_sec,
        loiter_radius_km=loiter_radius_km,
        loiter_min_minutes=loiter_min_minutes,
    )
    warnings = validate_payload(
        payload if isinstance(payload, dict) else {},
        required_keys=("id", "replay", "loiter", "geofences"),
        warnings=[],
    )
    if isinstance(payload, dict) and not payload.get("replay"):
        warnings.append("No replay history available.")
    return attach_meta(
        payload if isinstance(payload, dict) else {"meta": {}},
        route="/api/trackers/analysis",
        source="trackers",
        warnings=warnings,
    )


@router.post("/api/trackers/analysis")
def tracker_analysis_custom(
    request: TrackerAnalysisRequest,
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    payload = trackers.analyze_tracker(
        request.tracker_id,
        window_sec=request.window_sec,
        loiter_radius_km=request.loiter_radius_km,
        loiter_min_minutes=request.loiter_min_minutes,
        geofences=[item.model_dump() for item in request.geofences],
    )
    warnings = validate_payload(
        payload if isinstance(payload, dict) else {},
        required_keys=("id", "replay", "loiter", "geofences"),
        warnings=[],
    )
    if isinstance(payload, dict) and not payload.get("replay"):
        warnings.append("No replay history available.")
    return attach_meta(
        payload if isinstance(payload, dict) else {"meta": {}},
        route="/api/trackers/analysis",
        source="trackers",
        warnings=warnings,
    )
