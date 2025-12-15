from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Dict, List, Optional, Tuple

from modules.market_data.finnhub_client import FinnhubWrapper
from modules.market_data.yfinance_client import YahooWrapper


class ValuationEngine:
    """\
    Valuation engine for pricing ticker-based holdings, with a safe fallback path.

    Design goals:
        - Never raise in normal UI flows.
        - Always return predictable keys for quote lookups.
        - Support a separate manual/off-market valuation stream (estimated).
    """

    def __init__(
        self,
        finnhub_client: Optional[FinnhubWrapper] = None,
        yahoo_client: Optional[YahooWrapper] = None,
        logger: Any = None
    ):
        self.finnhub = finnhub_client if finnhub_client is not None else FinnhubWrapper()
        self.yahoo = yahoo_client if yahoo_client is not None else YahooWrapper()
        self.logger = logger

    def _log(self, level: str, message: str) -> None:
        if self.logger is None:
            return
        try:
            fn = getattr(self.logger, level, None)
            if callable(fn):
                fn(message)
        except Exception:
            return

    @staticmethod
    def _normalize_ticker(raw: str) -> str:
        return (raw or "").strip().upper()

    # -------------------------------
    # Public: Quote & history fetches
    # -------------------------------

    def get_quote_data(self, ticker: str) -> Dict[str, Any]:
        """\
        Lightweight quote lookup used by multiple UI flows.

        Always returns a dict with at least:
            - ticker, price, change, pct, change_pct, source, timestamp, error
        Never raises.
        """
        t = self._normalize_ticker(ticker)
        ts = int(time.time())

        if not t:
            return {
                "ticker": "",
                "price": 0.0,
                "change": 0.0,
                "pct": 0.0,
                "change_pct": 0.0,
                "currency": "USD",
                "timestamp": ts,
                "source": "N/A",
                "error": "Empty ticker",
            }

        # 1) Finnhub (fast)
        try:
            fh = self.finnhub.get_quote(t)
            if isinstance(fh, dict) and fh.get("price"):
                pct = float(fh.get("percent", 0.0) or 0.0)
                chg = float(fh.get("change", 0.0) or 0.0)
                price = float(fh.get("price", 0.0) or 0.0)
                return {
                    "ticker": t,
                    "price": price,
                    "change": chg,
                    "pct": pct,
                    "change_pct": pct,  # alias for UI compatibility
                    "currency": "USD",
                    "timestamp": ts,
                    "source": "Finnhub",
                    "error": "",
                }
        except Exception:
            pass

        # 2) Yahoo (fallback)
        try:
            yd = self.yahoo.get_detailed_quote(t, period="1d", interval="15m")
            if isinstance(yd, dict) and not yd.get("error") and float(yd.get("price", 0.0) or 0.0) > 0:
                pct = float(yd.get("pct", 0.0) or 0.0)
                chg = float(yd.get("change", 0.0) or 0.0)
                price = float(yd.get("price", 0.0) or 0.0)
                return {
                    "ticker": t,
                    "price": price,
                    "change": chg,
                    "pct": pct,
                    "change_pct": pct,
                    "currency": "USD",
                    "timestamp": ts,
                    "source": "Yahoo",
                    "error": "",
                }
        except Exception:
            pass

        return {
        "ticker": t,
        "price": 0.0,
        "change": 0.0,
        "pct": 0.0,
        "change_pct": 0.0,
        "currency": "USD",
        "timestamp": ts,
        "source": "N/A",
        "error": f"Could not fetch live price for {t}",
        }

    def get_detailed_data(self, ticker: str) -> Dict[str, Any]:
        """\
        Fetches richer data used for account/portfolio tables (includes history for sparklines).
        Prefers Yahoo for history, falls back to Finnhub for price-only.
        """
        t = self._normalize_ticker(ticker)

        try:
            data = self.yahoo.get_detailed_quote(t, period="1mo", interval="1d")
            if isinstance(data, dict) and "error" not in data:
                # Ensure key consistency
                data["ticker"] = data.get("ticker", t)
                data["pct"] = float(data.get("pct", 0.0) or 0.0)
                data["change"] = float(data.get("change", 0.0) or 0.0)
                data["price"] = float(data.get("price", 0.0) or 0.0)
                return data
        except Exception as ex:
            self._log("warning", f"Yahoo detailed fetch failed for {t}: {ex}")

        # Fallback: Finnhub price-only
        q = self.get_quote_data(t)
        return {
            "ticker": t,
            "name": t,
            "sector": "N/A",
            "mkt_cap": None,
            "price": float(q.get("price", 0.0) or 0.0),
            "change": float(q.get("change", 0.0) or 0.0),
            "pct": float(q.get("pct", 0.0) or 0.0),
            "high": 0.0,
            "low": 0.0,
            "volume": 0,
            "history": [],
        }

    # -------------------------------
    # Portfolio valuation
    # -------------------------------

    def calculate_portfolio_value(self, holdings: Dict[str, float]) -> Tuple[float, Dict[str, Any]]:
        """\
        Threaded calculation of market-priced holdings.

        Returns:
            (total_market_value, enriched_holdings)

        enriched_holdings[ticker] includes:
            - quantity, price, market_value, change, pct, change_pct, history, sector, name
        """
        total_value = 0.0
        enriched_holdings: Dict[str, Any] = {}

        if not holdings:
            return 0.0, enriched_holdings

        tickers = [self._normalize_ticker(t) for t in list(holdings.keys()) if str(t).strip()]
        unique_tickers = sorted(set(tickers))

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_ticker = {executor.submit(self.get_detailed_data, t): t for t in unique_tickers}

            for future in concurrent.futures.as_completed(future_to_ticker):
                t = future_to_ticker[future]
                data: Dict[str, Any] = {}
                try:
                    data = future.result()
                except Exception as ex:
                    self._log("warning", f"Detailed quote failed for {t}: {ex}")
                    data = {"price": 0.0, "change": 0.0, "pct": 0.0, "history": [], "sector": "N/A", "name": t}

                qty = 0.0
                try:
                    if t in holdings:
                        qty = float(holdings.get(t, 0.0) or 0.0)
                    else:
                        for k, v in holdings.items():
                            if self._normalize_ticker(k) == t:
                                qty = float(v or 0.0)
                                break
                except Exception:
                    qty = 0.0

                price = float(data.get("price", 0.0) or 0.0)
                mkt_val = price * qty
                total_value += mkt_val

                pct = float(data.get("pct", 0.0) or 0.0)
                enriched_holdings[t] = {
                    "ticker": t,
                    "name": data.get("name", t),
                    "sector": data.get("sector", "N/A"),
                    "quantity": qty,
                    "price": price,
                    "market_value": mkt_val,
                    "change": float(data.get("change", 0.0) or 0.0),
                    "pct": pct,
                    "change_pct": pct,  # manager reads change_pct in a few places
                    "history": data.get("history", []) or [],
                    "mkt_cap": data.get("mkt_cap", None),
                }

        return total_value, enriched_holdings

    # -------------------------------
    # Manual / off-market valuation
    # -------------------------------

    def calculate_manual_holdings_value(self, manual_holdings: List[Dict[str, Any]]) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Computes estimated total for manual/off-market assets.

        Accepts entries that provide either:
        - unit_price + quantity, or
        - total_value

        Returns:
        (manual_total_value, normalized_entries_sorted_desc)
        """
        total = 0.0
        normalized: List[Dict[str, Any]] = []

        if not manual_holdings:
            return 0.0, normalized

        for raw in manual_holdings:
            if not isinstance(raw, dict):
                continue

            name = str(raw.get("name", "")).strip() or "Manual Asset"
            currency = str(raw.get("currency", "USD")).strip() or "USD"
            notes = str(raw.get("notes", "")).strip()

            # quantity
            try:
                qty = float(raw.get("quantity", 0.0) or 0.0)
            except Exception:
                qty = 0.0

            # unit_price
            unit_price = None
            try:
                if raw.get("unit_price") is not None and str(raw.get("unit_price")).strip() != "":
                    unit_price = float(raw.get("unit_price"))
            except Exception:
                unit_price = None

            # total_value
            total_value = None
            try:
                if raw.get("total_value") is not None and str(raw.get("total_value")).strip() != "":
                    total_value = float(raw.get("total_value"))
            except Exception:
                total_value = None

            if total_value is None:
                if unit_price is None:
                    total_value = 0.0
                else:
                    total_value = unit_price * qty
            else:
                if unit_price is None and qty > 0:
                    unit_price = total_value / qty

            total += float(total_value or 0.0)

            normalized.append({
                "name": name,
                "quantity": float(qty),
                "unit_price": float(unit_price or 0.0),
                "total_value": float(total_value or 0.0),
                "currency": currency,
                "notes": notes,
            })

        normalized.sort(key=lambda x: x.get("total_value", 0.0), reverse=True)
        return total, normalized

    # -------------------------------
    # Aggregate history (dashboard)
    # -------------------------------

    def generate_synthetic_portfolio_history(self, enriched_data: Dict[str, Any], holdings: Dict[str, float]) -> List[float]:
        """\
        Reconstructs the portfolio's aggregate history (for a main dashboard chart).
        """
        if not enriched_data or not holdings:
            return []

        histories: List[List[float]] = []
        quantities: List[float] = []

        for t, info in enriched_data.items():
            hist = info.get("history", []) or []
            if not hist:
                continue
            try:
                qty = float(info.get("quantity", holdings.get(t, 0.0)) or 0.0)
            except Exception:
                qty = 0.0
            histories.append([float(x) for x in hist if x is not None])
            quantities.append(qty)

        if not histories:
            return []

        min_len = min(len(h) for h in histories if h)
        if min_len <= 0:
            return []

        out: List[float] = []
        idx = 0
        while idx < min_len:
            total = 0.0
            j = 0
            while j < len(histories):
                try:
                    total += histories[j][idx] * quantities[j]
                except Exception:
                    pass
                j += 1
            out.append(total)
            idx += 1

        return out
