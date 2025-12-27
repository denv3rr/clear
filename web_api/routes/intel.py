from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from modules.market_data.intel import MarketIntel, rank_news_items
from web_api.auth import require_api_key

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
    return report


@router.get("/api/intel/weather")
def intel_weather(
    region: str = Query("Global"),
    industry: str = Query("all"),
    _auth: None = Depends(require_api_key),
):
    intel = MarketIntel()
    return intel.weather_report(region_name=region, industry_filter=industry)


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
    return intel.conflict_report(
        region_name=region,
        industry_filter=industry,
        enabled_sources=enabled_sources,
        categories=category_list,
    )


@router.get("/api/intel/news")
def intel_news(
    region: str = Query("Global"),
    industry: str = Query("all"),
    tickers: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    force: bool = Query(False),
    _auth: None = Depends(require_api_key),
):
    intel = MarketIntel()
    payload = intel.fetch_news_signals(force=force)
    items = payload.get("items", []) if payload else []
    ticker_list = _split_list(tickers)
    if items:
        items = rank_news_items(items, tickers=ticker_list, region=region, industry=industry)
        items = items[:limit]
    return {
        "items": items,
        "cached": payload.get("cached", False),
        "stale": payload.get("stale", False),
        "skipped": payload.get("skipped", []),
        "health": payload.get("health", {}),
    }
