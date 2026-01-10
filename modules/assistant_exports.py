from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalize_source(source: Dict[str, Any]) -> Dict[str, Any]:
    route = source.get("route") or "unknown"
    source_name = source.get("source") or "unknown"
    timestamp = source.get("timestamp")
    normalized = {"route": str(route), "source": str(source_name)}
    if isinstance(timestamp, (int, float)):
        normalized["timestamp"] = int(timestamp)
    return normalized


def normalize_assistant_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    question = str(entry.get("question") or "").strip()
    answer = str(entry.get("answer") or "").strip() or "No response available."
    confidence = str(entry.get("confidence") or "Low").strip() or "Low"
    warnings = [
        str(item) for item in _as_list(entry.get("warnings")) if str(item).strip()
    ]
    sources = [
        _normalize_source(source)
        for source in _as_list(entry.get("sources"))
        if isinstance(source, dict)
    ]
    if not sources:
        warnings.append("No data sources were returned.")
    return {
        "question": question,
        "answer": answer,
        "confidence": confidence,
        "warnings": warnings,
        "sources": sources,
    }


def normalize_assistant_response(response: Dict[str, Any]) -> Dict[str, Any]:
    entry = normalize_assistant_entry(response)
    normalized = {
        "answer": entry["answer"],
        "confidence": entry["confidence"],
        "warnings": entry["warnings"],
        "sources": entry["sources"],
    }
    routing = response.get("routing")
    if isinstance(routing, dict):
        normalized["routing"] = routing
    return normalized


def build_assistant_export(
    history: Iterable[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
    generated_by: str = "assistant",
) -> Dict[str, Any]:
    normalized_history = [normalize_assistant_entry(item) for item in history]
    scope = format_scope(context or {})
    lineage = _extract_lineage(normalized_history)
    return {
        "version": 1,
        "generated_at": int(time.time()),
        "generated_by": generated_by,
        "scope": scope,
        "context": context or {},
        "methodology": {
            "engine": "rule_based_v1",
            "description": "Deterministic keyword routing with validated data sources.",
            "inputs": list((context or {}).keys()),
        },
        "lineage": lineage,
        "entries": normalized_history,
    }


def render_assistant_export_markdown(export_payload: Dict[str, Any]) -> str:
    lines = [
        "# Assistant History Export",
        "",
        f"Generated: {export_payload.get('generated_at')}",
        f"Scope: {export_payload.get('scope')}",
        "",
        "## Methodology",
        f"- Engine: {export_payload.get('methodology', {}).get('engine')}",
        f"- Description: {export_payload.get('methodology', {}).get('description')}",
        "",
        "## Data Lineage",
    ]
    lineage = export_payload.get("lineage") or []
    if lineage:
        for item in lineage:
            route = item.get("route", "unknown")
            source = item.get("source", "unknown")
            lines.append(f"- {route} ({source})")
    else:
        lines.append("- No data sources returned.")
    lines.append("")
    lines.append("## History")
    entries = export_payload.get("entries") or []
    if not entries:
        lines.append("No assistant history entries available.")
        return "\n".join(lines)
    for entry in entries:
        lines.append("")
        lines.append(f"### Question: {entry.get('question', '')}")
        lines.append(f"Answer: {entry.get('answer', '')}")
        lines.append(f"Confidence: {entry.get('confidence', '')}")
        warnings = entry.get("warnings") or []
        if warnings:
            lines.append(f"Warnings: {', '.join(warnings)}")
        sources = entry.get("sources") or []
        if sources:
            source_list = ", ".join(
                f"{src.get('route', 'unknown')} ({src.get('source', 'unknown')})"
                for src in sources
            )
            lines.append(f"Sources: {source_list}")
    return "\n".join(lines)


def format_scope(context: Dict[str, Any]) -> str:
    region = str(context.get("region") or "Global").strip() or "Global"
    industry = str(context.get("industry") or "all").strip() or "all"
    parts = [region, industry]
    tickers = _format_list(context.get("tickers"))
    if tickers:
        parts.append(f"Tickers: {tickers}")
    client_id = str(context.get("client_id") or "").strip()
    if client_id:
        parts.append(f"Client: {client_id}")
    account_id = str(context.get("account_id") or "").strip()
    if account_id:
        parts.append(f"Account: {account_id}")
    return " \u2022 ".join(parts)


def _format_list(value: Any) -> str:
    items = [str(item).strip() for item in _as_list(value) if str(item).strip()]
    return ", ".join(items)


def _extract_lineage(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    lineage = []
    for entry in entries:
        for source in entry.get("sources", []) or []:
            key = (source.get("route"), source.get("source"))
            if key in seen:
                continue
            seen.add(key)
            lineage.append(source)
    return lineage
