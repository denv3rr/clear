from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from modules.market_data.intel import MarketIntel
from modules.market_data.scene_payloads import (
    build_intel_scene,
    build_overview_scene,
    build_tracker_scene,
)
from modules.market_data.trackers import GlobalTrackers
from web_api.auth import require_api_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


def _split_list(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


def _parse_bbox(raw: Optional[str]) -> Optional[Tuple[float, float, float, float]]:
    if not raw:
        return None
    parts = [item.strip() for item in raw.split(",")]
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox must be min_lat,min_lon,max_lat,max_lon")
    try:
        min_lat, min_lon, max_lat, max_lon = (float(item) for item in parts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="bbox must contain numeric values") from exc
    if min_lat > max_lat or min_lon > max_lon:
        raise HTTPException(status_code=400, detail="bbox min values must be <= max values")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise HTTPException(status_code=400, detail="bbox latitude must be within [-90, 90]")
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        raise HTTPException(status_code=400, detail="bbox longitude must be within [-180, 180]")
    return min_lat, min_lon, max_lat, max_lon


@router.get("/api/osint/scene/trackers")
def osint_tracker_scene(
    mode: str = Query("combined", pattern="^(combined|flights|ships)$"),
    point_limit: int = Query(24, ge=1, le=200),
    trail_limit: int = Query(8, ge=0, le=50),
    category: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    operator: Optional[str] = Query(None),
    bbox: Optional[str] = Query(None),
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    snapshot = trackers.get_snapshot(mode=mode)
    bbox_tuple = _parse_bbox(bbox)
    snapshot = trackers.apply_filters(
        snapshot,
        category=category,
        country=country,
        operator=operator,
        bbox=bbox_tuple,
    )
    scene = build_tracker_scene(
        snapshot,
        history_fetcher=trackers.get_history,
        mode=mode,
        point_limit=point_limit,
        trail_limit=trail_limit,
        filters={
            key: value
            for key, value in {
                "category": category,
                "country": country,
                "operator": operator,
                "bbox": bbox_tuple,
            }.items()
            if value not in (None, "")
        },
    )
    warnings = list(snapshot.get("warnings", []) or [])
    warnings.extend(scene.get("meta", {}).get("warnings", []) or [])
    warnings = validate_payload(
        scene,
        required_keys=("scene_id", "camera_defaults", "timeline", "layers", "focus_targets"),
        non_empty_keys=("layers",),
        warnings=warnings,
    )
    return attach_meta(
        scene,
        route="/api/osint/scene/trackers",
        source="trackers",
        warnings=warnings,
    )


@router.get("/api/osint/scene/intel")
def osint_intel_scene(
    industry: str = Query("all"),
    categories: Optional[str] = Query(None),
    sources: Optional[str] = Query(None),
    _auth: None = Depends(require_api_key),
):
    intel = MarketIntel()
    category_list = _split_list(categories)
    enabled_sources = _split_list(sources)
    scene = build_intel_scene(
        intel,
        industry_filter=industry,
        categories=category_list,
        enabled_sources=enabled_sources,
    )
    warnings = validate_payload(
        scene,
        required_keys=("scene_id", "camera_defaults", "timeline", "layers", "focus_targets"),
        non_empty_keys=("layers",),
        warnings=list(scene.get("meta", {}).get("warnings", []) or []),
    )
    return attach_meta(
        scene,
        route="/api/osint/scene/intel",
        source="intel",
        warnings=warnings,
    )


@router.get("/api/osint/scene/overview")
def osint_overview_scene(
    mode: str = Query("combined", pattern="^(combined|flights|ships)$"),
    point_limit: int = Query(24, ge=1, le=200),
    trail_limit: int = Query(8, ge=0, le=50),
    category: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    operator: Optional[str] = Query(None),
    bbox: Optional[str] = Query(None),
    industry: str = Query("all"),
    categories: Optional[str] = Query(None),
    sources: Optional[str] = Query(None),
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    snapshot = trackers.get_snapshot(mode=mode)
    bbox_tuple = _parse_bbox(bbox)
    snapshot = trackers.apply_filters(
        snapshot,
        category=category,
        country=country,
        operator=operator,
        bbox=bbox_tuple,
    )
    intel = MarketIntel()
    scene = build_overview_scene(
        snapshot,
        intel,
        history_fetcher=trackers.get_history,
        mode=mode,
        point_limit=point_limit,
        trail_limit=trail_limit,
        tracker_filters={
            key: value
            for key, value in {
                "category": category,
                "country": country,
                "operator": operator,
                "bbox": bbox_tuple,
            }.items()
            if value not in (None, "")
        },
        industry_filter=industry,
        categories=_split_list(categories),
        enabled_sources=_split_list(sources),
    )
    warnings = validate_payload(
        scene,
        required_keys=("scene_id", "camera_defaults", "timeline", "layers", "focus_targets"),
        non_empty_keys=("layers",),
        warnings=list(scene.get("meta", {}).get("warnings", []) or []),
    )
    return attach_meta(
        scene,
        route="/api/osint/scene/overview",
        source="trackers+intel",
        warnings=warnings,
    )
