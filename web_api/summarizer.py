from __future__ import annotations

import re
import time
from typing import Any, Dict, Iterable, List, Optional

from modules.client_store import DbClientStore
from modules.market_data.intel import MarketIntel
from modules.market_data.trackers import GlobalTrackers
from modules.view_models import list_clients
from modules.assistant_exports import normalize_assistant_response
from web_api.summarizer_rules import (
    RULES,
    handle_account_detail,
    handle_client_detail,
    handle_clients,
    handle_news,
    handle_trackers,
)


SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

ALLOWED_CONTEXT_BY_ENTRY = {
    "dashboard": {"region", "industry", "tickers", "sources"},
    "clients": {"client_id", "account_id"},
    "reports": {"client_id", "account_id"},
    "osint": {"region", "industry", "tickers", "sources"},
    "trackers": {"region", "industry", "tickers", "sources"},
    "intel": {"region", "industry", "tickers", "sources"},
    "news": {"region", "industry", "tickers", "sources"},
    "system": set(),
    "unknown": {"region", "industry", "tickers", "sources"},
}

PATH_GUARD_RE = re.compile(
    r"(file://|[A-Za-z]:\\\\|[A-Za-z]:/|\\\.\.\\|/\.\./|/etc/|/var/|/usr/|/home/|/users/)",
    re.IGNORECASE,
)


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


def _sanitize_identifier(
    value: Any,
    label: str,
    warnings: List[str],
) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if not value:
        return None
    if not SAFE_ID_RE.match(value):
        warnings.append(f"Invalid {label} format; ignoring.")
        return None
    return value


def _normalize_context(context: Optional[dict]) -> tuple[Dict[str, Any], List[str]]:
    if not isinstance(context, dict):
        return {}, []
    warnings: List[str] = []
    normalized: Dict[str, Any] = {
        "region": _read_context_value(context, "region", "Global"),
        "industry": _read_context_value(context, "industry", "all"),
    }
    tickers = _as_list(_read_context_value(context, "tickers", None))
    if tickers:
        normalized["tickers"] = tickers
    client_id = _sanitize_identifier(context.get("client_id"), "client ID", warnings)
    if client_id:
        normalized["client_id"] = client_id
    account_id = _sanitize_identifier(
        context.get("account_id"), "account ID", warnings
    )
    if account_id:
        normalized["account_id"] = account_id
    return normalized, warnings


def _filter_context_by_entry(
    entry: Optional[str],
    context: Optional[dict],
) -> tuple[Dict[str, Any], List[str], bool]:
    if not isinstance(context, dict):
        return {}, [], False
    key = (entry or "unknown").strip().lower()
    allowed = ALLOWED_CONTEXT_BY_ENTRY.get(key, ALLOWED_CONTEXT_BY_ENTRY["unknown"])
    warnings: List[str] = []
    filtered: Dict[str, Any] = {}
    denied = False
    for item_key, value in context.items():
        if item_key in allowed:
            filtered[item_key] = value
            continue
        warnings.append(f"Context field '{item_key}' not allowed for entry '{key}'.")
        if item_key in ("client_id", "account_id"):
            denied = True
    return filtered, warnings, denied


def _guard_path_access(question: str, warnings: List[str]) -> bool:
    if PATH_GUARD_RE.search(question or ""):
        warnings.append("Blocked filesystem/path access request.")
        return True
    return False


def _find_account(client: Dict[str, Any], account_id: str) -> Optional[Dict[str, Any]]:
    accounts = client.get("accounts") or []
    for account in accounts:
        if str(account.get("account_id") or "").strip() == account_id:
            return account
    return None


def _resolve_client_scope(
    context: Dict[str, Any],
    warnings: List[str],
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    client_id = context.get("client_id")
    account_id = context.get("account_id")
    if not client_id and not account_id:
        return None, None

    store = DbClientStore()
    client: Optional[Dict[str, Any]] = None
    account: Optional[Dict[str, Any]] = None

    if client_id:
        client = store.fetch_client(client_id)
        if client is None:
            warnings.append("Client ID not found.")
            context.pop("client_id", None)
            client_id = None
        elif account_id:
            account = _find_account(client, account_id)
            if account is None:
                warnings.append("Account ID not found for client.")
                context.pop("account_id", None)
                account_id = None

    if account_id and not client_id:
        matches: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        for candidate in store.fetch_all_clients():
            match = _find_account(candidate, account_id)
            if match:
                matches.append((candidate, match))
        if len(matches) == 1:
            client, account = matches[0]
            context["client_id"] = client.get("client_id") or context.get("client_id")
        elif len(matches) > 1:
            warnings.append(
                "Account ID matches multiple clients; provide a client ID."
            )
            context.pop("account_id", None)
        else:
            warnings.append("Account ID not found.")
            context.pop("account_id", None)
    return client, account


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
    entry: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Summarizes the data from the different sources based on a set of rules.
    """
    question_lower = question.lower()
    enabled_sources = _as_list(sources)
    scoped_context, scope_warnings, denied = _filter_context_by_entry(entry, context)
    context_data, context_warnings = _normalize_context(scoped_context)
    warnings: List[str] = []
    warnings.extend(scope_warnings)
    warnings.extend(context_warnings)
    if _guard_path_access(question, warnings):
        response = {
            "answer": "Filesystem or path access requests are not permitted.",
            "sources": [],
            "confidence": "Low",
            "warnings": warnings,
            "routing": {"rule": "guardrail", "handler": "path_access_blocked"},
        }
        return normalize_assistant_response(response)
    if denied:
        response = {
            "answer": "Assistant scope denied for this page context.",
            "sources": [],
            "confidence": "Low",
            "warnings": warnings,
            "routing": {"rule": "scope", "handler": "scope_denied"},
        }
        return normalize_assistant_response(response)

    for rule_details in RULES.values():
        for keyword in rule_details["keywords"]:
            if keyword in question_lower:
                handler_name = rule_details["handler"]
                routing = {
                    "rule": rule_details.get("name") or handler_name.replace("handle_", ""),
                    "handler": handler_name,
                }
                if handler_name == "handle_clients":
                    client, account = _resolve_client_scope(context_data, warnings)
                    if account:
                        client_id = client.get("client_id") if client else "unknown"
                        account_id = account.get("account_id") or "unknown"
                        response = {
                            "answer": handle_account_detail(
                                account,
                                client_label=client.get("name") if client else None,
                            ),
                            "sources": [
                                _build_source(
                                    f"/api/clients/{client_id}/accounts/{account_id}",
                                    "database",
                                )
                            ],
                            "confidence": "Medium",
                            "warnings": warnings,
                            "routing": routing,
                        }
                        return normalize_assistant_response(response)
                    if client:
                        client_id = client.get("client_id") or "unknown"
                        response = {
                            "answer": handle_client_detail(client),
                            "sources": [
                                _build_source(f"/api/clients/{client_id}", "database")
                            ],
                            "confidence": "Medium",
                            "warnings": warnings,
                            "routing": routing,
                        }
                        return normalize_assistant_response(response)
                    clients = get_clients()
                    count = len(clients.get("clients", []))
                    if count == 0:
                        warnings.append("No clients available.")
                    response = {
                        "answer": handle_clients(clients),
                        "sources": [_build_source("/api/clients", "database")],
                        "confidence": "Medium" if count else "Low",
                        "warnings": warnings,
                        "routing": routing,
                    }
                    return normalize_assistant_response(response)
                if handler_name == "handle_news":
                    news = get_news(context_data, enabled_sources)
                    count = len(news.get("items", []))
                    if news.get("stale"):
                        warnings.append("News feed marked stale.")
                    if count == 0:
                        warnings.append("News feed returned no items.")
                    response = {
                        "answer": handle_news(news),
                        "sources": [_build_source("/api/intel/news", "intel")],
                        "confidence": "Medium" if count else "Low",
                        "warnings": warnings,
                        "routing": routing,
                    }
                    return normalize_assistant_response(response)
                if handler_name == "handle_trackers":
                    trackers = get_trackers()
                    count = trackers.get("count", 0)
                    if count == 0:
                        warnings.append("No tracker points returned.")
                    response = {
                        "answer": handle_trackers(trackers),
                        "sources": [
                            _build_source("/api/trackers/snapshot", "trackers")
                        ],
                        "confidence": "Medium" if count else "Low",
                        "warnings": warnings,
                        "routing": routing,
                    }
                    return normalize_assistant_response(response)

    response = {
        "answer": "No deterministic assistant rule matched this question.",
        "sources": [],
        "confidence": "Low",
        "warnings": warnings + ["Unsupported assistant query."],
        "routing": {"rule": "unmatched", "handler": None},
    }
    return normalize_assistant_response(response)
