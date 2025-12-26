from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


Timestamp = Optional[datetime]
PriceLookup = Callable[[datetime], Optional[float]]


def normalize_ticker(raw: str) -> str:
    return (raw or "").strip().upper()


def parse_timestamp(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    upper = text.upper()
    if upper in ("LEGACY", "AGGREGATE", "UNKNOWN"):
        return None
    if upper.startswith("CUSTOM"):
        text = text.replace("CUSTOM", "").strip(" ()")
    if text.endswith("Z"):
        text = text[:-1]

    try:
        return datetime.fromisoformat(text)
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def format_timestamp(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%S")


def compute_weighted_avg_cost(lots: Iterable[Dict[str, Any]]) -> float:
    total_qty = 0.0
    total_cost = 0.0
    for lot in lots or []:
        if not isinstance(lot, dict):
            continue
        try:
            qty = float(lot.get("qty", 0.0) or 0.0)
            basis = float(lot.get("basis", 0.0) or 0.0)
        except Exception:
            continue
        if qty <= 0:
            continue
        total_qty += qty
        total_cost += qty * basis
    if total_qty <= 0:
        return 0.0
    return total_cost / total_qty


def select_nearest_price(
    series: Iterable[Tuple[datetime, float]],
    target: datetime,
) -> Optional[float]:
    points = [(ts, price) for ts, price in series if isinstance(ts, datetime)]
    if not points:
        return None
    nearest = min(points, key=lambda item: abs(item[0] - target))
    try:
        return float(nearest[1])
    except Exception:
        return None


def build_lot_entry(
    qty: float,
    basis: Optional[float],
    timestamp: Optional[datetime],
    source: str,
    kind: str = "lot",
    price_lookup: Optional[PriceLookup] = None,
) -> Dict[str, Any]:
    if qty is None or qty <= 0:
        raise ValueError("Quantity must be positive.")
    if basis is not None and basis < 0:
        raise ValueError("Cost basis must be non-negative.")

    resolved_basis = basis
    resolved_source = source
    if resolved_basis is None and timestamp and price_lookup:
        price = price_lookup(timestamp)
        if price is not None and price > 0:
            resolved_basis = float(price)
            if resolved_source:
                resolved_source = f"{resolved_source}+HISTORICAL"
            else:
                resolved_source = "HISTORICAL"

    if resolved_basis is None:
        raise ValueError("Cost basis unavailable.")

    label = format_timestamp(timestamp) if timestamp else "AGGREGATE"
    return {
        "qty": float(qty),
        "basis": float(resolved_basis),
        "timestamp": label,
        "source": str(resolved_source or "").strip().upper(),
        "kind": str(kind or "lot").strip().lower(),
    }


@dataclass
class HoldingSummary:
    ticker: str
    total_qty: float
    avg_cost: float


def summarize_holding(ticker: str, lots: Iterable[Dict[str, Any]]) -> HoldingSummary:
    normalized = normalize_ticker(ticker)
    total_qty = 0.0
    for lot in lots or []:
        if not isinstance(lot, dict):
            continue
        try:
            qty = float(lot.get("qty", 0.0) or 0.0)
        except Exception:
            qty = 0.0
        if qty <= 0:
            continue
        total_qty += qty
    return HoldingSummary(
        ticker=normalized,
        total_qty=float(total_qty),
        avg_cost=float(compute_weighted_avg_cost(lots)),
    )
