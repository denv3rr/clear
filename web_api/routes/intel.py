from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from modules.market_data.intel import MarketIntel, get_intel_meta, rank_news_items
from web_api.auth import require_api_key
from web_api.view_model import attach_meta, validate_payload

router = APIRouter()


def _split_list(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


@router.get("/api/intel/summary")
def intel_summary(
    region: str = Query("Global"),
    industry: str = Query("all"),
    categories: Optional[str] = Query(None),
    sources: Optional[str] = Query(None),
    _auth: None = Depends(require_api_key),
):
    intel = MarketIntel()
    enabled_sources = _split_list(sources)
    category_list = _split_list(categories)
    report = intel.combined_report(
        region_name=region,
        industry_filter=industry,
        enabled_sources=enabled_sources,
        categories=category_list,
    )
    warnings = validate_payload(
        report if isinstance(report, dict) else {},
        required_keys=("summary", "sections"),
        warnings=[],
    )
    if isinstance(report, dict) and not report.get("summary"):
        warnings.append("Intel summary empty.")
    return attach_meta(
        report,
        route="/api/intel/summary",
        source="intel",
        warnings=warnings,
    )


@router.get("/api/intel/meta")
def intel_meta(_auth: None = Depends(require_api_key)):
    payload = get_intel_meta()
    warnings = validate_payload(
        payload,
        required_keys=("regions", "industries", "sources"),
        warnings=[],
    )
    if not payload.get("regions"):
        warnings.append("Intel metadata regions missing.")
    return attach_meta(
        payload,
        route="/api/intel/meta",
        source="intel",
        warnings=warnings,
    )


@router.get("/api/intel/weather")
def intel_weather(
    region: str = Query("Global"),
    industry: str = Query("all"),
    _auth: None = Depends(require_api_key),
):
    intel = MarketIntel()
    payload = intel.weather_report(region_name=region, industry_filter=industry)
    warnings = validate_payload(
        payload if isinstance(payload, dict) else {},
        required_keys=("summary", "sections"),
        warnings=[],
    )
    if isinstance(payload, dict) and not payload.get("summary"):
        warnings.append("Weather report summary missing.")
    return attach_meta(
        payload,
        route="/api/intel/weather",
        source="intel",
        warnings=warnings,
    )


@router.get("/api/intel/conflict")
def intel_conflict(
    region: str = Query("Global"),
    industry: str = Query("all"),
    categories: Optional[str] = Query(None),
    sources: Optional[str] = Query(None),
    _auth: None = Depends(require_api_key),
):
    intel = MarketIntel()
    enabled_sources = _split_list(sources)
    category_list = _split_list(categories)
    payload = intel.conflict_report(
        region_name=region,
        industry_filter=industry,
        enabled_sources=enabled_sources,
        categories=category_list,
    )
    warnings = validate_payload(
        payload if isinstance(payload, dict) else {},
        required_keys=("summary", "sections"),
        warnings=[],
    )
    if isinstance(payload, dict) and not payload.get("summary"):
        warnings.append("Conflict report summary missing.")
    return attach_meta(
        payload,
        route="/api/intel/conflict",
        source="intel",
        warnings=warnings,
    )


@router.get("/api/intel/news")
def intel_news(
    region: str = Query("Global"),
    industry: str = Query("all"),
    tickers: Optional[str] = Query(None),
    sources: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    force: bool = Query(False),
    _auth: None = Depends(require_api_key),
):
    intel = MarketIntel()
    enabled_sources = _split_list(sources)
    payload = intel.fetch_news_signals(force=force, enabled_sources=enabled_sources)
    items = payload.get("items", []) if payload else []
    ticker_list = _split_list(tickers)
    if items:
        items = intel.filter_news_items(items, region, industry, tickers=ticker_list)
        items = items[:limit]
    payload = {
        "items": items,
        "cached": payload.get("cached", False),
        "stale": payload.get("stale", False),
        "skipped": payload.get("skipped", []),
        "health": payload.get("health", {}),
    }
    warnings = validate_payload(
        payload,
        required_keys=("items", "cached", "stale", "skipped", "health"),
        warnings=[],
    )
    if not items:
        warnings.append("News feed returned no items.")
    if payload.get("stale"):
        warnings.append("News feed marked stale.")
    return attach_meta(
        payload,
        route="/api/intel/news",
        source="intel",
        warnings=warnings,
    )
