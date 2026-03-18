from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from modules.market_data.intel import MarketIntel
from modules.market_data.scene_payloads import build_intel_scene, build_tracker_scene
from modules.market_data.trackers import GlobalTrackers
from web_api.auth import require_api_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


def _split_list(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


@router.get("/api/osint/scene/trackers")
def osint_tracker_scene(
    mode: str = Query("combined", pattern="^(combined|flights|ships)$"),
    point_limit: int = Query(24, ge=1, le=200),
    trail_limit: int = Query(8, ge=0, le=50),
    _auth: None = Depends(require_api_key),
):
    trackers = GlobalTrackers()
    snapshot = trackers.get_snapshot(mode=mode)
    scene = build_tracker_scene(
        snapshot,
        history_fetcher=trackers.get_history,
        mode=mode,
        point_limit=point_limit,
        trail_limit=trail_limit,
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
