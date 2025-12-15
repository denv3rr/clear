import yfinance as yf
import pandas as pd
import numpy as np

import time
import io
import warnings
import logging
import contextlib

# Suppress yfinance and urllib3 warnings/logs
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

class YahooWrapper:
    """
    Yahoo Finance wrapper (yfinance) with:
    - silent downloads (no stderr spam / FutureWarnings in UI)
    - cached failures (skip repeated slow lookups for bad symbols)
    - lightweight TTL caching for quotes/snapshots to reduce repeated network pulls
    """
    
    # Nested Macro Tickers
    MACRO_TICKERS = {

        "Commodities": {
            # Energy
            "CL=F": "Crude Oil WTI",
            "BZ=F": "Brent Crude",
            "NG=F": "Natural Gas",
            "RB=F": "RBOB Gasoline",
            "HO=F": "Heating Oil",

            # Metals
            "GC=F": "Gold",
            "SI=F": "Silver",
            "HG=F": "Copper",
            "PL=F": "Platinum",
            "PA=F": "Palladium",

            # Agriculture
            "ZC=F": "Corn",
            "ZW=F": "Wheat",
            "ZS=F": "Soybeans",
            "KC=F": "Coffee",
            "SB=F": "Sugar",
            "CC=F": "Cocoa",
            "CT=F": "Cotton",

            # Livestock
            "LE=F": "Live Cattle",
            "GF=F": "Feeder Cattle",
            "HE=F": "Lean Hogs"
        },

        "Indices": {
            # U.S.
            "^GSPC": "S&P 500",
            "^DJI": "Dow Jones",
            "^IXIC": "Nasdaq Composite",
            "^RUT": "Russell 2000",
            "^VIX": "VIX Volatility Index",

            # Europe
            "^FTSE": "FTSE 100",
            "^GDAXI": "DAX (Germany)",
            "^FCHI": "CAC 40 (France)",

            # Asia
            "^N225": "Nikkei 225",
            "^HSI": "Hang Seng Index",
            "^STI": "Singapore Straits Times",
            "000001.SS": "Shanghai Composite",
            "^KS11": "KOSPI",

            # Lat/SAM
            "^BVSP": "Bovespa (Brazil)",
            "^MXX": "IPC (Mexico)",
        },

        "FX": {
            # Majors
            "EURUSD=X": "EUR/USD",
            "GBPUSD=X": "GBP/USD",
            "USDJPY=X": "USD/JPY",
            "AUDUSD=X": "AUD/USD",
            "NZDUSD=X": "NZD/USD",

            # USD crosses
            "USDCAD=X": "USD/CAD",
            "USDCHF=X": "USD/CHF",
            "USDSEK=X": "USD/SEK",
            "USDNOK=X": "USD/NOK",
            "USDZAR=X": "USD/ZAR",

            # EM FX
            "USDMXN=X": "USD/MXN",
            "USDTRY=X": "USD/TRY",
            "USDCNY=X": "USD/CNY",
            "USDHKD=X": "USD/HKD",
            "USDINR=X": "USD/INR"
        },

        "Rates": {
            # U.S. yields
            "^IRX": "13W Treasury Bill Yield",
            "^FVX": "5Y Treasury Yield",
            "^TNX": "10Y Treasury Yield",
            "^TYX": "30Y Treasury Yield",

            # Volatility indices
            "^MOVE": "Bond Volatility Index",

            # Global rates (confirmed)
            "^FTSE": "UK 10Y Gilt Yield",
            "^N225": "Japan 10Y JGB Yield"
        },

        "Crypto": {
            "BTC-USD": "Bitcoin",
            "ETH-USD": "Ethereum",
            "SOL-USD": "Solana",
            "XRP-USD": "Ripple",
            "ADA-USD": "Cardano"
        },

        "Macro ETFs": {
            # Equities
            "SPY": "S&P 500 ETF",
            "QQQ": "Nasdaq 100 ETF",
            "IWM": "Russell 2000 ETF",

            # Global macro exposures
            "EEM": "Emerging Markets ETF",
            "VEA": "Developed Markets ex-US ETF",

            # Rates & Credit
            "TLT": "20+ Year Treasury Bond ETF",
            "IEF": "7-10 Year Treasury ETF",
            "HYG": "High Yield Corporate Bond ETF",
            "LQD": "Investment Grade Corporate Bond ETF",

            # Currencies
            "UUP": "US Dollar Index ETF",
            "FXE": "Euro Currency ETF",
            "FXY": "Japanese Yen ETF",

            # Commodities
            "GLD": "Gold ETF",
            "SLV": "Silver ETF",
            "DBC": "Broad Commodity ETF",
            "USO": "Oil ETF",

            # Shipping & global trade
            "BDRY": "Dry Bulk Shipping ETF",
            "SEA": "Global Shipping ETF"
        }
    }

    # Failure cache (avoid repeated lag on known-bad tickers)
    _BAD_SYMBOL_UNTIL: Dict[str, int] = {}
    _BAD_TTL_SECONDS = 1800  # 30 minutes

    # Last missing symbols from the most recent snapshot call
    _LAST_MISSING: List[str] = []

    # Snapshot cache (period, interval) -> (ts, results)
    _SNAPSHOT_CACHE: Dict[Tuple[str, str], Tuple[int, List[Dict[str, Any]]]] = {}
    _SNAPSHOT_TTL_SECONDS = 60  # 1 minute

    # Detailed quote cache (ticker, period, interval) -> (ts, data)
    _DETAILED_CACHE: Dict[Tuple[str, str, str], Tuple[int, Dict[str, Any]]] = {}
    _DETAILED_TTL_SECONDS = 30  # 30 seconds

    @staticmethod
    def _now() -> int:
        return int(time.time())

    @classmethod
    def _is_bad(cls, symbol: str) -> bool:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return True
        until = int(cls._BAD_SYMBOL_UNTIL.get(sym, 0) or 0)
        return cls._now() < until

    @classmethod
    def _mark_bad(cls, symbol: str, ttl_seconds: int = None) -> None:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return
        ttl = int(ttl_seconds if ttl_seconds is not None else cls._BAD_TTL_SECONDS)
        cls._BAD_SYMBOL_UNTIL[sym] = cls._now() + max(60, ttl)

    @staticmethod
    def _silent_download(tickers, **kwargs) -> pd.DataFrame:
        buf = io.StringIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            warnings.simplefilter("ignore", category=UserWarning)
            with contextlib.redirect_stderr(buf):
                return yf.download(tickers, **kwargs)

    @classmethod
    def get_last_missing_symbols(cls) -> List[str]:
        return list(cls._LAST_MISSING)

    # ----------------------- Detailed Quote -----------------------

    def get_detailed_quote(self, ticker: str, period: str = "1d", interval: str = "15m") -> Dict[str, Any]:
        sym = str(ticker or "").strip().upper()
        if not sym:
            return {"error": "Empty ticker"}

        if YahooWrapper._is_bad(sym):
            return {"error": f"No data (cached failure): {sym}"}

        cache_key = (sym, str(period), str(interval))
        cached = YahooWrapper._DETAILED_CACHE.get(cache_key)
        if cached:
            ts, data = cached
            if (YahooWrapper._now() - int(ts or 0)) <= YahooWrapper._DETAILED_TTL_SECONDS:
                return data

        try:
            buf = io.StringIO()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=FutureWarning)
                warnings.simplefilter("ignore", category=UserWarning)
                with contextlib.redirect_stderr(buf):
                    stock = yf.Ticker(sym)
                    hist = stock.history(period=period, interval=interval, auto_adjust=True)

            if hist is None or hist.empty or ("Close" not in hist.columns):
                YahooWrapper._mark_bad(sym)
                return {"error": f"No history returned for {sym}"}

            closes = hist["Close"].dropna()
            if closes.empty:
                YahooWrapper._mark_bad(sym)
                return {"error": f"No close series returned for {sym}"}

            current = float(closes.iloc[-1])
            start = float(closes.iloc[0])
            change = current - start
            pct = (change / start) * 100 if start != 0 else 0.0

            high = float(hist["High"].max()) if "High" in hist.columns and not hist["High"].dropna().empty else current
            low = float(hist["Low"].min()) if "Low" in hist.columns and not hist["Low"].dropna().empty else current
            volume = float(hist["Volume"].sum()) if "Volume" in hist.columns and not hist["Volume"].dropna().empty else 0.0

            name = sym
            sector = "N/A"
            mkt_cap = None
            try:
                info = getattr(stock, "info", {}) or {}
                name = info.get("shortName") or info.get("longName") or sym
                sector = info.get("sector") or "N/A"
                mkt_cap = info.get("marketCap")
            except Exception:
                pass

            data = {
                "ticker": sym,
                "name": name,
                "sector": sector,
                "mkt_cap": mkt_cap,
                "price": float(current),
                "change": float(change),
                "pct": float(pct),
                "high": float(high),
                "low": float(low),
                "volume": int(volume),
                "history": closes.tail(40).tolist(),
            }

            YahooWrapper._DETAILED_CACHE[cache_key] = (YahooWrapper._now(), data)
            return data

        except Exception as e:
            YahooWrapper._mark_bad(sym)
            return {"error": str(e)}

    # ----------------------- Macro Snapshot -----------------------

    @staticmethod
    def _chunk(seq: List[str], size: int) -> List[List[str]]:
        out = []
        i = 0
        while i < len(seq):
            out.append(seq[i:i + size])
            i += size
        return out

    def get_macro_snapshot(self, period: str = "1d", interval: str = "15m") -> List[Dict[str, Any]]:
        key = (str(period), str(interval))

        cached = YahooWrapper._SNAPSHOT_CACHE.get(key)
        if cached:
            ts, data = cached
            if (YahooWrapper._now() - int(ts or 0)) <= YahooWrapper._SNAPSHOT_TTL_SECONDS:
                return data

        ticker_meta: Dict[str, Dict[str, str]] = {}
        for cat, symbols in YahooWrapper.MACRO_TICKERS.items():
            for sym, name in (symbols or {}).items():
                s = str(sym or "").strip().upper()
                if s:
                    ticker_meta[s] = {"name": name, "category": cat}

        requested = list(ticker_meta.keys())
        flat_list = [s for s in requested if not YahooWrapper._is_bad(s)]

        results: List[Dict[str, Any]] = []
        missing: List[str] = []

        def process_download_frame(data: pd.DataFrame, symbols: List[str]) -> None:
            nonlocal results, missing
            if data is None or data.empty:
                for s in symbols:
                    missing.append(s)
                return

            is_multi = isinstance(data.columns, pd.MultiIndex)

            for sym in symbols:
                meta = ticker_meta.get(sym, {"name": sym, "category": "Other"})
                try:
                    if is_multi:
                        if ("Close" not in data.columns.get_level_values(0)):
                            missing.append(sym)
                            YahooWrapper._mark_bad(sym)
                            continue
                        if sym not in data["Close"].columns:
                            missing.append(sym)
                            YahooWrapper._mark_bad(sym)
                            continue
                        closes = data["Close"][sym].dropna()
                        highs = data["High"][sym].dropna() if "High" in data else pd.Series(dtype=float)
                        lows = data["Low"][sym].dropna() if "Low" in data else pd.Series(dtype=float)
                        vols = data["Volume"][sym].dropna() if "Volume" in data else pd.Series(dtype=float)
                    else:
                        closes = data.get("Close", pd.Series(dtype=float)).dropna()
                        highs = data.get("High", pd.Series(dtype=float)).dropna()
                        lows = data.get("Low", pd.Series(dtype=float)).dropna()
                        vols = data.get("Volume", pd.Series(dtype=float)).dropna()

                    if closes.empty:
                        missing.append(sym)
                        YahooWrapper._mark_bad(sym)
                        continue

                    current = float(closes.iloc[-1])
                    start = float(closes.iloc[0])
                    change = current - start
                    pct = (change / start) * 100 if start != 0 else 0.0

                    high = float(highs.max()) if not highs.empty else current
                    low = float(lows.min()) if not lows.empty else current
                    volume = float(vols.iloc[-1]) if not vols.empty else 0.0

                    results.append({
                        "ticker": sym,
                        "name": meta.get("name", sym),
                        "category": meta.get("category", "Other"),
                        "price": float(current),
                        "change": float(change),
                        "pct": float(pct),
                        "high": float(high),
                        "low": float(low),
                        "volume": int(volume) if not pd.isna(volume) else 0,
                        "history": closes.tail(20).tolist(),
                    })
                except Exception:
                    missing.append(sym)
                    YahooWrapper._mark_bad(sym)

        try:
            data = YahooWrapper._silent_download(
                flat_list,
                period=period,
                interval=interval,
                progress=False,
                group_by="column",
                auto_adjust=True,
                threads=False,
            )

            if data is None or data.empty:
                for chunk in YahooWrapper._chunk(flat_list, 25):
                    d = YahooWrapper._silent_download(
                        chunk,
                        period=period,
                        interval=interval,
                        progress=False,
                        group_by="column",
                        auto_adjust=True,
                        threads=False,
                    )
                    process_download_frame(d, chunk)
            else:
                process_download_frame(data, flat_list)

        except Exception:
            cached = YahooWrapper._SNAPSHOT_CACHE.get(key)
            if cached:
                return cached[1]
            return []

        YahooWrapper._LAST_MISSING = sorted(set(missing))

        if results:
            YahooWrapper._SNAPSHOT_CACHE[key] = (YahooWrapper._now(), results)

        if not results:
            cached = YahooWrapper._SNAPSHOT_CACHE.get(key)
            if cached:
                return cached[1]

        return results