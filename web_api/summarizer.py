from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

from modules.client_store import DbClientStore
from modules.market_data.intel import MarketIntel
from modules.market_data.trackers import GlobalTrackers
from modules.view_models import list_clients
from web_api.summarizer_rules import RULES, handle_clients, handle_news, handle_trackers


def _build_source(route: str, source: str) -> Dict[str, Any]:
    return {"route": route, "source": source, "timestamp": int(time.time())}


def _as_list(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or None
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
        return items or None
    return None


def _read_context_value(context: Optional[dict], key: str, default: Any) -> Any:
    if not isinstance(context, dict):
        return default
    value = context.get(key, default)
    return value if value not in (None, "") else default


def get_clients() -> Dict[str, Any]:
    """
    Fetches client data from the database.
    """
    store = DbClientStore()
    clients = store.fetch_all_clients()
    return {"clients": list_clients(clients)}


def get_news(context: Optional[dict], sources: Optional[List[str]]) -> Dict[str, Any]:
    """
    Fetches news data from the intel module.
    """
    intel = MarketIntel()
    payload = intel.fetch_news_signals(force=False, enabled_sources=sources)
    items = payload.get("items", []) if payload else []
    region = _read_context_value(context, "region", "Global")
    industry = _read_context_value(context, "industry", "all")
    tickers = _as_list(_read_context_value(context, "tickers", None))
    if items:
        items = intel.filter_news_items(items, region, industry, tickers=tickers)
    return {
        "items": items,
        "cached": payload.get("cached", False),
        "stale": payload.get("stale", False),
        "skipped": payload.get("skipped", []),
        "health": payload.get("health", {}),
    }


def get_trackers() -> Dict[str, Any]:
    """
    Fetches tracker data from the tracker module.
    """
    trackers = GlobalTrackers()
    return trackers.get_snapshot(mode="combined")


def summarize(
    question: str,
    context: Optional[dict],
    sources: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    Summarizes the data from the different sources based on a set of rules.
    """
    question_lower = question.lower()
    enabled_sources = _as_list(sources)
    warnings: List[str] = []

    for rule_details in RULES.values():
        for keyword in rule_details["keywords"]:
            if keyword in question_lower:
                handler_name = rule_details["handler"]
                if handler_name == "handle_clients":
                    clients = get_clients()
                    count = len(clients.get("clients", []))
                    if count == 0:
                        warnings.append("No clients available.")
                    return {
                        "answer": handle_clients(clients),
                        "sources": [_build_source("/api/clients", "database")],
                        "confidence": "Medium" if count else "Low",
                        "warnings": warnings,
                    }
                if handler_name == "handle_news":
                    news = get_news(context, enabled_sources)
                    count = len(news.get("items", []))
                    if news.get("stale"):
                        warnings.append("News feed marked stale.")
                    if count == 0:
                        warnings.append("News feed returned no items.")
                    return {
                        "answer": handle_news(news),
                        "sources": [_build_source("/api/intel/news", "intel")],
                        "confidence": "Medium" if count else "Low",
                        "warnings": warnings,
                    }
                if handler_name == "handle_trackers":
                    trackers = get_trackers()
                    count = trackers.get("count", 0)
                    if count == 0:
                        warnings.append("No tracker points returned.")
                    return {
                        "answer": handle_trackers(trackers),
                        "sources": [
                            _build_source("/api/trackers/snapshot", "trackers")
                        ],
                        "confidence": "Medium" if count else "Low",
                        "warnings": warnings,
                    }

    return {
        "answer": "I'm sorry, I don't understand the question. Please try rephrasing it.",
        "sources": [],
        "confidence": "Low",
        "warnings": ["Unsupported assistant query."],
    }
