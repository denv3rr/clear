from __future__ import annotations

import json
import os
from typing import Dict, Optional

DEFAULT_OPERATORS: Dict[str, Dict[str, str]] = {
    "AAL": {"name": "American Airlines", "country": "United States"},
    "DAL": {"name": "Delta Air Lines", "country": "United States"},
    "UAL": {"name": "United Airlines", "country": "United States"},
    "SWA": {"name": "Southwest Airlines", "country": "United States"},
    "JBU": {"name": "JetBlue", "country": "United States"},
    "BAW": {"name": "British Airways", "country": "United Kingdom"},
    "DLH": {"name": "Lufthansa", "country": "Germany"},
    "AFR": {"name": "Air France", "country": "France"},
    "KLM": {"name": "KLM", "country": "Netherlands"},
    "ANA": {"name": "All Nippon Airways", "country": "Japan"},
    "JAL": {"name": "Japan Airlines", "country": "Japan"},
    "QFA": {"name": "Qantas", "country": "Australia"},
    "SIA": {"name": "Singapore Airlines", "country": "Singapore"},
    "CPA": {"name": "Cathay Pacific", "country": "Hong Kong"},
    "UAE": {"name": "Emirates", "country": "United Arab Emirates"},
    "QTR": {"name": "Qatar Airways", "country": "Qatar"},
    "THY": {"name": "Turkish Airlines", "country": "Turkey"},
    "IBE": {"name": "Iberia", "country": "Spain"},
    "KAL": {"name": "Korean Air", "country": "South Korea"},
    "AIC": {"name": "Air India", "country": "India"},
    "UPS": {"name": "UPS Airlines", "country": "United States"},
    "FDX": {"name": "FedEx", "country": "United States"},
}

_CACHE: Optional[Dict[str, Dict[str, str]]] = None
_CACHE_MTIME: Optional[int] = None


def _load_registry(path: str) -> Dict[str, Dict[str, str]]:
    try:
        with open(path, "r", encoding="ascii") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    parsed: Dict[str, Dict[str, str]] = {}
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        name = str(value.get("name") or "").strip()
        country = str(value.get("country") or "").strip()
        if not name:
            continue
        parsed[str(key).upper()] = {"name": name, "country": country}
    return parsed


def get_operator_registry(path: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    global _CACHE, _CACHE_MTIME
    registry_path = path or os.path.join("config", "flight_operators.json")
    try:
        mtime = int(os.path.getmtime(registry_path))
    except Exception:
        mtime = None
    if _CACHE is None or mtime != _CACHE_MTIME:
        extra = _load_registry(registry_path) if mtime else {}
        merged = {**DEFAULT_OPERATORS}
        merged.update({k: v for k, v in extra.items() if isinstance(v, dict)})
        _CACHE = merged
        _CACHE_MTIME = mtime
    return _CACHE or DEFAULT_OPERATORS


def get_operator_info(code: Optional[str]) -> Dict[str, str]:
    if not code:
        return {"name": "", "country": ""}
    registry = get_operator_registry()
    info = registry.get(code.upper())
    if not info:
        return {"name": "", "country": ""}
    return {"name": info.get("name", ""), "country": info.get("country", "")}
