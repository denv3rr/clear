from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional, Sequence


def attach_meta(
    payload: Dict[str, Any],
    *,
    route: str,
    source: str,
    warnings: Optional[Iterable[str]] = None,
    status: str = "ok",
) -> Dict[str, Any]:
    meta = {
        "route": route,
        "source": source,
        "timestamp": int(time.time()),
        "status": status,
        "warnings": list(warnings or []),
    }
    existing = payload.get("meta")
    if isinstance(existing, dict):
        meta = {**existing, **meta}
    payload["meta"] = meta
    return payload


def validate_payload(
    payload: Dict[str, Any],
    *,
    required_keys: Sequence[str] = (),
    non_empty_keys: Sequence[str] = (),
    warnings: Optional[Iterable[str]] = None,
) -> List[str]:
    collected: List[str] = list(warnings or [])
    for key in required_keys:
        if key not in payload:
            collected.append(f"Missing required field: {key}")
    for key in non_empty_keys:
        value = payload.get(key)
        if value is None or value == "" or value == [] or value == {}:
            collected.append(f"Empty field: {key}")
    return collected
