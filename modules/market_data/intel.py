import json
import os
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

from modules.market_data.collectors import (
    fetch_news_items,
    load_cached_news,
    store_cached_news,
    CONFLICT_CATEGORIES,
    DEFAULT_SOURCES,
)


@dataclass
class RegionSpec:
    name: str
    lat: float
    lon: float
    industries: List[str]


REGIONS: List[RegionSpec] = [
    RegionSpec("Global", 20.0, 0.0, ["energy", "agriculture", "shipping", "aviation"]),
    RegionSpec("North America", 39.8, -98.6, ["energy", "agriculture", "logistics", "tech"]),
    RegionSpec("Europe", 50.0, 10.0, ["industry", "energy", "manufacturing", "finance"]),
    RegionSpec("Middle East", 24.0, 45.0, ["energy", "shipping", "defense"]),
    RegionSpec("Asia-Pacific", 22.0, 113.0, ["manufacturing", "shipping", "tech"]),
    RegionSpec("Latin America", -15.0, -60.0, ["agriculture", "mining", "energy"]),
    RegionSpec("Africa", 1.0, 20.0, ["mining", "energy", "agriculture"]),
]


def get_intel_meta() -> Dict[str, object]:
    regions = [{"name": region.name, "industries": list(region.industries)} for region in REGIONS]
    industries = sorted({industry for region in REGIONS for industry in region.industries})
    sources = [collector.name for collector in DEFAULT_SOURCES]
    return {
        "regions": regions,
        "industries": industries,
        "categories": list(CONFLICT_CATEGORIES),
        "sources": sources,
    }


def _region_by_name(name: str) -> RegionSpec:
    for region in REGIONS:
        if region.name.lower() == name.lower():
            return region
    return REGIONS[0]


def _impact_for_weather(temp_c: Optional[float], wind_ms: Optional[float], precip_mm: Optional[float]) -> List[str]:
    impacts: List[str] = []
    if wind_ms is not None and wind_ms >= 20:
        impacts.append("High wind may disrupt aviation and shipping.")
    elif wind_ms is not None and wind_ms >= 15:
        impacts.append("Gusty conditions could slow air and sea logistics.")
    if precip_mm is not None and precip_mm >= 10:
        impacts.append("Heavy precipitation may impact logistics and agriculture.")
    if temp_c is not None and (temp_c >= 35 or temp_c <= -10):
        impacts.append("Temperature extremes can stress energy demand and crops.")
    return impacts


def _impact_for_conflict(themes: List[str]) -> List[str]:
    impacts: List[str] = []
    theme_text = " ".join(themes).lower()
    if "oil" in theme_text or "gas" in theme_text or "energy" in theme_text:
        impacts.append("Energy supply risks elevated.")
    if "transport" in theme_text or "shipping" in theme_text or "port" in theme_text:
        impacts.append("Shipping and logistics risk elevated.")
    if "military" in theme_text or "security" in theme_text or "attack" in theme_text:
        impacts.append("Defense-related industries may see volatility.")
    if "food" in theme_text or "agri" in theme_text or "crop" in theme_text:
        impacts.append("Agriculture supply risk elevated.")
    if "cyber" in theme_text or "telecom" in theme_text or "tech" in theme_text:
        impacts.append("Tech and infrastructure risk elevated.")
    return impacts


def _risk_level(score: int) -> str:
    if score >= 9:
        return "Severe"
    if score >= 6:
        return "High"
    if score >= 3:
        return "Moderate"
    return "Low"


def _score_weather(
    temp_c: Optional[float],
    wind_ms: Optional[float],
    precip_mm: Optional[float],
    precip_24h: float,
    wind_max: float,
    temp_min: float,
    temp_max: float,
) -> Tuple[int, List[str]]:
    score = 0
    signals: List[str] = []
    if wind_ms is not None and wind_ms >= 20:
        score += 3
        signals.append("Sustained high wind")
    elif wind_ms is not None and wind_ms >= 15:
        score += 2
        signals.append("Elevated wind")
    if precip_mm is not None and precip_mm >= 10:
        score += 2
        signals.append("Heavy precipitation")
    if precip_24h >= 25:
        score += 2
        signals.append("High 24h precipitation")
    if temp_c is not None and (temp_c >= 35 or temp_c <= -10):
        score += 2
        signals.append("Temperature extremes")
    if (temp_max - temp_min) >= 20:
        score += 1
        signals.append("Wide temperature range")
    return score, signals


def _score_conflict(article_count: int, themes: List[str]) -> Tuple[int, List[str]]:
    score = 0
    signals: List[str] = []
    if article_count >= 20:
        score += 4
        signals.append("High volume of conflict reports")
    elif article_count >= 10:
        score += 3
        signals.append("Elevated conflict reporting")
    elif article_count >= 5:
        score += 2
        signals.append("Moderate conflict reporting")
    elif article_count > 0:
        score += 1
        signals.append("Some conflict reporting")
    theme_text = " ".join(themes).lower()
    if "military" in theme_text or "attack" in theme_text or "security" in theme_text:
        score += 3
        signals.append("Security-related signals")
    if "oil" in theme_text or "gas" in theme_text or "energy" in theme_text:
        score += 2
        signals.append("Energy exposure signals")
    if "shipping" in theme_text or "port" in theme_text or "transport" in theme_text:
        score += 2
        signals.append("Logistics exposure signals")
    return score, signals


def _confidence_weather(temp_c: Optional[float], wind_ms: Optional[float], precip_mm: Optional[float]) -> str:
    present = sum(1 for val in (temp_c, wind_ms, precip_mm) if val is not None)
    if present == 3:
        return "High"
    if present == 2:
        return "Medium"
    return "Low"


def _confidence_conflict(article_count: int) -> str:
    if article_count >= 15:
        return "High"
    if article_count >= 5:
        return "Medium"
    return "Low"


def _filter_conflict_news(
    items: List[Dict[str, object]],
    region_name: str,
    categories: Optional[List[str]] = None,
) -> List[Dict[str, object]]:
    region_l = (region_name or "").lower()
    categories_l = [c.lower() for c in (categories or []) if c]
    filtered = []
    for item in items:
        title = str(item.get("title", "") or "")
        tags = item.get("tags", []) or []
        regions = item.get("regions", []) or []
        industries = item.get("industries", []) or []
        has_conflict = "conflict" in tags or any(word in title.lower() for word in ("war", "strike", "protest", "attack", "conflict", "ceasefire"))
        in_region = not region_l or any(region_l in r.lower() for r in regions)
        derived = set()
        if has_conflict:
            derived.add("conflict")
        for industry in industries:
            derived.add(str(industry).lower())
        if regions:
            derived.add("world")
        else:
            derived.add("general")
        if categories_l:
            if not any(cat in derived for cat in categories_l):
                continue
        if has_conflict and in_region:
            filtered.append(item)
    return filtered


DEFAULT_TICKER_ALIASES: Dict[str, List[str]] = {
    "AAPL": ["APPLE", "APPLE INC"],
    "MSFT": ["MICROSOFT", "MICROSOFT CORP"],
    "GOOGL": ["ALPHABET", "GOOGLE"],
    "GOOG": ["ALPHABET", "GOOGLE"],
    "AMZN": ["AMAZON", "AMAZON.COM"],
    "TSLA": ["TESLA", "TESLA INC"],
    "NVDA": ["NVIDIA", "NVIDIA CORP"],
    "META": ["META", "FACEBOOK", "META PLATFORMS"],
    "BRK.B": ["BERKSHIRE", "BERKSHIRE HATHAWAY"],
    "SPY": ["S&P 500", "SPDR S&P 500", "SPDR 500"],
    "IVV": ["S&P 500", "ISHARES CORE S&P 500"],
    "VOO": ["S&P 500", "VANGUARD S&P 500"],
    "VTI": ["TOTAL STOCK MARKET", "VANGUARD TOTAL STOCK MARKET"],
    "QQQ": ["NASDAQ 100", "INVESCO QQQ"],
    "IWM": ["RUSSELL 2000", "ISHARES RUSSELL 2000"],
    "DIA": ["DOW JONES", "SPDR DOW JONES"],
    "GLD": ["GOLD", "SPDR GOLD"],
    "TLT": ["TREASURY", "20+ YEAR TREASURY"],
    "LQD": ["INVESTMENT GRADE CREDIT", "ISHARES IBOXIG"],
}

_ALIAS_CACHE: Optional[Dict[str, List[str]]] = None
_ALIAS_CACHE_MTIME: Optional[int] = None
_ALIAS_CACHE_PATH: Optional[str] = None
_SETTINGS_MTIME: Optional[int] = None
_SETTINGS_ALIAS_PATH: Optional[str] = None


def _merge_aliases(
    base: Dict[str, List[str]],
    extra: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    merged: Dict[str, List[str]] = {k: list(v) for k, v in base.items()}
    for key, values in extra.items():
        key_u = str(key).upper()
        merged.setdefault(key_u, [])
        for value in values:
            val = str(value).strip()
            if val and val not in merged[key_u]:
                merged[key_u].append(val)
    return merged


def load_ticker_aliases(path: str) -> Dict[str, List[str]]:
    try:
        with open(path, "r", encoding="ascii") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    parsed: Dict[str, List[str]] = {}
    for key, value in data.items():
        if isinstance(value, list):
            parsed[str(key).upper()] = [str(v) for v in value if str(v).strip()]
        elif isinstance(value, str):
            parsed[str(key).upper()] = [value]
    return parsed


def validate_alias_file(path: str) -> Tuple[bool, str]:
    try:
        with open(path, "r", encoding="ascii") as f:
            data = json.load(f)
    except Exception as exc:
        return False, f"Invalid JSON: {exc}"
    if not isinstance(data, dict):
        return False, "Alias file must be a JSON object."
    for key, value in data.items():
        if isinstance(value, list):
            if not all(isinstance(v, str) and v.strip() for v in value):
                return False, f"Alias list for {key} must contain non-empty strings."
        elif isinstance(value, str):
            if not value.strip():
                return False, f"Alias string for {key} must be non-empty."
        else:
            return False, f"Alias for {key} must be a string or list of strings."
    return True, "ok"


def _aliases_path_from_settings(settings_path: str) -> Optional[str]:
    try:
        with open(settings_path, "r", encoding="ascii") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    news = data.get("news", {})
    if not isinstance(news, dict):
        return None
    alias_path = news.get("aliases_file")
    if not isinstance(alias_path, str) or not alias_path.strip():
        return None
    alias_path = alias_path.strip()
    if os.path.isabs(alias_path):
        return alias_path
    return os.path.normpath(os.path.join(os.getcwd(), alias_path))


def get_ticker_aliases(path: Optional[str] = None) -> Dict[str, List[str]]:
    global _ALIAS_CACHE, _ALIAS_CACHE_MTIME, _ALIAS_CACHE_PATH
    global _SETTINGS_MTIME, _SETTINGS_ALIAS_PATH
    if path is None:
        settings_path = os.path.join("config", "settings.json")
        try:
            settings_mtime = int(os.path.getmtime(settings_path))
        except Exception:
            settings_mtime = None
        if settings_mtime != _SETTINGS_MTIME:
            _SETTINGS_ALIAS_PATH = _aliases_path_from_settings(settings_path)
            _SETTINGS_MTIME = settings_mtime
    alias_path = path or _SETTINGS_ALIAS_PATH or os.path.join("config", "news_aliases.json")
    try:
        mtime = int(os.path.getmtime(alias_path))
    except Exception:
        mtime = None
    if _ALIAS_CACHE is None or mtime != _ALIAS_CACHE_MTIME or alias_path != _ALIAS_CACHE_PATH:
        extra = load_ticker_aliases(alias_path) if mtime else {}
        _ALIAS_CACHE = _merge_aliases(DEFAULT_TICKER_ALIASES, extra)
        _ALIAS_CACHE_MTIME = mtime
        _ALIAS_CACHE_PATH = alias_path
    return _ALIAS_CACHE


def _normalize_text_for_match(text: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9]+", " ", (text or "").upper()).strip()
    return re.sub(r"\s+", " ", cleaned)


def _ticker_matches_title(
    title: str,
    tickers: Optional[List[str]],
    ticker_aliases: Optional[Dict[str, List[str]]] = None,
) -> bool:
    if not tickers:
        return False
    title_upper = f" {_normalize_text_for_match(title)} "
    alias_map = ticker_aliases or DEFAULT_TICKER_ALIASES
    for ticker in tickers:
        if len(ticker) < 2:
            continue
        ticker_norm = _normalize_text_for_match(ticker)
        if ticker_norm and f" {ticker_norm} " in title_upper:
            return True
        for alias in alias_map.get(ticker.upper(), []):
            alias_norm = _normalize_text_for_match(alias)
            if alias_norm and f" {alias_norm} " in title_upper:
                return True
    return False


def score_news_item(
    item: Dict[str, object],
    tickers: Optional[List[str]] = None,
    region: Optional[str] = None,
    industry: Optional[str] = None,
    ticker_aliases: Optional[Dict[str, List[str]]] = None,
) -> int:
    score = 0
    title = str(item.get("title", "") or "")
    title_lower = title.lower()
    regions = item.get("regions", []) or []
    industries = item.get("industries", []) or []
    tags = item.get("tags", []) or []
    published_ts = item.get("published_ts")

    alias_map = ticker_aliases or get_ticker_aliases()
    if _ticker_matches_title(title, tickers, ticker_aliases=alias_map):
        score += 6
    if industry and industry != "all" and industry in industries:
        score += 3
    if region and region != "Global" and region in regions:
        score += 2
    if tags:
        score += 1
    if published_ts:
        age_hours = max(0, (int(time.time()) - int(published_ts)) / 3600)
        if age_hours <= 24:
            score += 2
        elif age_hours <= 72:
            score += 1
    if "earnings" in title_lower or "guidance" in title_lower:
        score += 1
    return score


def score_news_items(
    items: List[Dict[str, object]],
    tickers: Optional[List[str]] = None,
    region: Optional[str] = None,
    industry: Optional[str] = None,
    ticker_aliases: Optional[Dict[str, List[str]]] = None,
) -> List[Tuple[int, Dict[str, object]]]:
    scored: List[Tuple[int, Dict[str, object]]] = []
    for item in items:
        scored.append((score_news_item(item, tickers, region, industry, ticker_aliases=ticker_aliases), item))
    scored.sort(key=lambda pair: (pair[0], pair[1].get("published_ts") or 0), reverse=True)
    return scored


def rank_news_items(
    items: List[Dict[str, object]],
    tickers: Optional[List[str]] = None,
    region: Optional[str] = None,
    industry: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, object]]:
    scored = score_news_items(items, tickers=tickers, region=region, industry=industry)
    ranked = [item for _, item in scored]
    if limit is not None:
        return ranked[:limit]
    return ranked


def news_cache_status(payload: Optional[Dict[str, object]]) -> str:
    if not isinstance(payload, dict):
        return "unknown"
    if payload.get("stale"):
        return "stale"
    if payload.get("items"):
        return "fresh"
    return "empty"


class WeatherIntel:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def fetch(self, region: RegionSpec) -> Dict[str, object]:
        params = {
            "latitude": region.lat,
            "longitude": region.lon,
            "current": "temperature_2m,wind_speed_10m,precipitation",
            "hourly": "temperature_2m,wind_speed_10m,precipitation",
            "forecast_days": 1,
            "timezone": "UTC",
        }
        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=8)
            if resp.status_code != 200:
                return {"error": f"Open-Meteo HTTP {resp.status_code}"}
            payload = resp.json()
        except Exception as exc:
            return {"error": f"Open-Meteo fetch failed: {exc}"}

        current = payload.get("current", {}) or {}
        temp = current.get("temperature_2m")
        wind = current.get("wind_speed_10m")
        precip = current.get("precipitation")

        hourly = payload.get("hourly", {}) or {}
        precip_series = hourly.get("precipitation") or []
        wind_series = hourly.get("wind_speed_10m") or []
        temp_series = hourly.get("temperature_2m") or []

        total_precip = sum(float(p) for p in precip_series if p is not None)
        max_wind = max([float(w) for w in wind_series if w is not None] or [0.0])
        max_temp = max([float(t) for t in temp_series if t is not None] or [0.0])
        min_temp = min([float(t) for t in temp_series if t is not None] or [0.0])

        impacts = _impact_for_weather(temp, wind, precip)
        return {
            "region": region.name,
            "temp_c": temp,
            "wind_ms": wind,
            "precip_mm": precip,
            "precip_24h": total_precip,
            "wind_max": max_wind,
            "temp_max": max_temp,
            "temp_min": min_temp,
            "impacts": impacts,
        }


class ConflictIntel:
    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    _health = {
        "fail_count": 0,
        "backoff_until": 0,
        "last_ok": None,
        "last_fail": None,
        "last_attempt": None,
    }

    def fetch(self, region: RegionSpec) -> Dict[str, object]:
        now = int(time.time())
        self._health["last_attempt"] = now
        backoff_until = int(self._health.get("backoff_until", 0) or 0)
        if now < backoff_until:
            return {"error": "GDELT is in cooldown. Try again later.", "cooldown": True}
        query = f"conflict OR war OR protest OR strike OR blockade sourcecountry:{region.name.split()[0]}"
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 25,
            "sort": "HybridRel",
        }
        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=8)
            if resp.status_code != 200:
                self._record_fail()
                return {"error": f"GDELT HTTP {resp.status_code}"}
            if not resp.text or not resp.text.strip():
                self._record_fail()
                return {"error": "GDELT returned an empty response."}
            if "application/json" not in str(resp.headers.get("Content-Type", "")).lower():
                self._record_fail()
                return {"error": "GDELT returned a non-JSON response."}
            try:
                payload = resp.json() or {}
            except Exception:
                self._record_fail()
                return {"error": "GDELT returned invalid JSON."}
        except Exception as exc:
            self._record_fail()
            return {"error": f"GDELT fetch failed: {exc}"}

        self._record_success()

        articles = payload.get("articles") or []
        themes: List[str] = []
        rows: List[Dict[str, object]] = []
        for art in articles[:12]:
            title = art.get("title", "Untitled")
            url = art.get("url", "")
            source = art.get("sourcecountry", "")
            seendate = art.get("seendate", "")
            art_themes = art.get("themes", []) or []
            if isinstance(art_themes, str):
                art_themes = [art_themes]
            themes.extend([str(t) for t in art_themes])
            rows.append({
                "title": title,
                "url": url,
                "source": source,
                "time": seendate,
                "themes": ", ".join(art_themes[:3]),
            })

        impacts = _impact_for_conflict(themes)
        return {
            "region": region.name,
            "count": len(articles),
            "articles": rows,
            "impacts": impacts,
        }

    def _record_success(self) -> None:
        self._health["fail_count"] = 0
        self._health["backoff_until"] = 0
        self._health["last_ok"] = int(time.time())

    def _record_fail(self) -> None:
        fails = int(self._health.get("fail_count", 0) or 0) + 1
        backoff = min(60 * fails, 900)
        self._health["fail_count"] = fails
        self._health["backoff_until"] = int(time.time()) + backoff
        self._health["last_fail"] = int(time.time())

    def health_status(self) -> Dict[str, object]:
        now = int(time.time())
        backoff_until = int(self._health.get("backoff_until", 0) or 0)
        last_attempt = self._health.get("last_attempt")
        if last_attempt is None and int(self._health.get("fail_count", 0) or 0) == 0:
            status = "idle"
        elif now < backoff_until:
            status = "cooldown"
        elif int(self._health.get("fail_count", 0) or 0) > 0:
            status = "warning"
        else:
            status = "ok"
        return {
            "status": status,
            "backoff_until": backoff_until,
            "fail_count": int(self._health.get("fail_count", 0) or 0),
            "last_ok": self._health.get("last_ok"),
            "last_fail": self._health.get("last_fail"),
            "last_attempt": last_attempt,
        }


class MarketIntel:
    def __init__(self):
        self.weather = WeatherIntel()
        self.conflict = ConflictIntel()
        self._news_cache_file = "data/intel_news.json"

    def fetch_news_signals(
        self,
        ttl_seconds: int = 600,
        force: bool = False,
        enabled_sources: Optional[List[str]] = None,
    ) -> Dict[str, object]:
        if not force:
            cached = load_cached_news(self._news_cache_file, ttl_seconds)
            if cached is not None:
                return {
                    "items": cached,
                    "cached": True,
                    "stale": False,
                    "skipped": [],
                    "health": {},
                }
        payload = fetch_news_items(limit=60, enabled=enabled_sources)
        items = payload.get("items", [])
        if items:
            store_cached_news(self._news_cache_file, items)
            return {
                "items": items,
                "cached": False,
                "stale": False,
                "skipped": payload.get("skipped", []),
                "health": payload.get("health", {}),
            }
        stale = load_cached_news(self._news_cache_file, ttl_seconds, allow_stale=True)
        if stale:
            return {
                "items": stale,
                "cached": True,
                "stale": True,
                "skipped": payload.get("skipped", []),
                "health": payload.get("health", {}),
            }
        return {
            "items": [],
            "cached": False,
            "stale": False,
            "skipped": payload.get("skipped", []),
            "health": payload.get("health", {}),
        }

    def _filter_news(
        self,
        items: List[Dict[str, object]],
        region_name: str,
        industry_filter: str,
        tickers: Optional[List[str]] = None,
    ) -> List[Dict[str, object]]:
        filtered = []
        for item in items:
            regions = item.get("regions", []) or []
            industries = item.get("industries", []) or []
            region_ok = True if region_name == "Global" else region_name in regions
            industry_ok = True if industry_filter == "all" else industry_filter in industries
            if region_ok and industry_ok:
                filtered.append(item)
        return rank_news_items(filtered, tickers=tickers, region=region_name, industry=industry_filter)

    def filter_news_items(
        self,
        items: List[Dict[str, object]],
        region_name: str,
        industry_filter: str,
        tickers: Optional[List[str]] = None,
    ) -> List[Dict[str, object]]:
        return self._filter_news(items, region_name, industry_filter, tickers=tickers)

    def _filter_impacts(self, impacts: List[str], industry_filter: str) -> List[str]:
        if not impacts or industry_filter == "all":
            return impacts
        key = industry_filter.lower()
        return [imp for imp in impacts if key in imp.lower()]

    def weather_report(self, region_name: str, industry_filter: str = "all") -> Dict[str, object]:
        region = _region_by_name(region_name)
        data = self.weather.fetch(region)
        if data.get("error"):
            return {
                "title": "Weather Impact Report",
                "summary": [str(data["error"])],
                "sections": [],
            }
        impacts = self._filter_impacts(data.get("impacts", []), industry_filter)
        score, signals = _score_weather(
            data.get("temp_c"),
            data.get("wind_ms"),
            data.get("precip_mm"),
            float(data.get("precip_24h") or 0.0),
            float(data.get("wind_max") or 0.0),
            float(data.get("temp_min") or 0.0),
            float(data.get("temp_max") or 0.0),
        )
        risk = _risk_level(score)
        confidence = _confidence_weather(data.get("temp_c"), data.get("wind_ms"), data.get("precip_mm"))
        summary = [
            f"Region: {region.name}",
            f"Temp: {data.get('temp_c', 'n/a')} C | Wind: {data.get('wind_ms', 'n/a')} m/s",
            f"24h Precip: {data.get('precip_24h', 0):.1f} mm | Wind Max: {data.get('wind_max', 0):.1f} m/s",
            f"Risk Level: {risk} (score {score}/10)",
            f"Confidence: {confidence}",
        ]
        if industry_filter != "all":
            summary.append(f"Industry Filter: {industry_filter}")
        if signals:
            summary.append("Signals: " + " ".join(signals[:2]))
        if impacts:
            summary.append("Impacts: " + " ".join(impacts[:2]))

        industries = ", ".join(region.industries)
        sections = [
            {
                "title": "Weather Details",
                "rows": [
                    ["Region", region.name],
                    ["Temp (C)", data.get("temp_c", "n/a")],
                    ["Wind (m/s)", data.get("wind_ms", "n/a")],
                    ["Precip (mm)", data.get("precip_mm", "n/a")],
                    ["24h Precip (mm)", f"{data.get('precip_24h', 0):.1f}"],
                    ["Temp Range (C)", f"{data.get('temp_min', 0):.1f} to {data.get('temp_max', 0):.1f}"],
                    ["Industries", industries],
                ],
            }
        ]
        if impacts:
            sections.append({
                "title": "Impact Signals",
                "rows": [[f"- {impact}", ""] for impact in impacts],
            })
        if signals:
            sections.append({
                "title": "Weather Signals",
                "rows": [[f"- {signal}", ""] for signal in signals],
            })
        sections.append({
            "title": "Outlook",
            "rows": [[self._weather_outlook(risk, region, industry_filter), ""]],
        })
        sections.append({
            "title": "Model Notes",
            "rows": [[f"Confidence: {confidence} | Signals: {len(signals)} | Impacts: {len(impacts)} | Scope: {region.name} | Industry: {industry_filter}", ""]],
        })
        sources = ["Open-Meteo"]
        news_cached = load_cached_news(self._news_cache_file, ttl_seconds=999999)
        if news_cached:
            filtered = self._filter_news(news_cached, region.name, industry_filter)
            if filtered:
                sections.append({
                    "title": "News Signals",
                    "rows": [[item.get("source", ""), item.get("title", "")[:90]] for item in filtered[:6]],
                })
                sources.extend(sorted({str(item.get("source", "")) for item in filtered if item.get("source")}))
        if sources:
            sections.append({
                "title": "Report Sources",
                "rows": [[source, ""] for source in sorted(set(sources))],
            })
        return {
            "title": "Weather Impact Report",
            "summary": summary,
            "sections": sections,
            "risk_level": risk,
            "risk_score": score,
            "confidence": confidence,
            "signals": signals,
            "impacts": impacts,
        }

    def conflict_report(
        self,
        region_name: str,
        industry_filter: str = "all",
        enabled_sources: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, object]:
        region = _region_by_name(region_name)
        news_payload = self.fetch_news_signals(
            ttl_seconds=600,
            enabled_sources=enabled_sources,
        )
        data = self.conflict.fetch(region)
        if data.get("error"):
            items = _filter_conflict_news(news_payload.get("items", []), region.name, categories=categories)
            themes: List[str] = []
            for item in items:
                themes.extend([str(t) for t in (item.get("tags") or [])])
                themes.extend([str(t) for t in (item.get("industries") or [])])
            score, signals = _score_conflict(len(items), themes)
            risk = _risk_level(score)
            confidence = _confidence_conflict(len(items))
            summary = [
                f"Region: {region.name}",
                f"Conflict signals sourced from RSS feeds ({len(items)} items).",
                f"Risk Level: {risk} (score {score}/10)",
                f"Confidence: {confidence}",
            ]
            if industry_filter != "all":
                summary.append(f"Industry Filter: {industry_filter}")
            sections: List[Dict[str, object]] = []
            if items:
                sections.append({
                    "title": "Conflict Signals (News)",
                    "rows": [[item.get("source", ""), item.get("title", "")[:90]] for item in items[:8]],
                })
            if signals:
                sections.append({
                    "title": "Conflict Signals",
                    "rows": [[f"- {signal}", ""] for signal in signals],
                })
            sources = sorted({str(item.get("source", "")) for item in items if item.get("source")})
            if sources:
                sections.append({
                    "title": "Report Sources",
                    "rows": [[source, ""] for source in sources],
                })
            return {
                "title": "Conflict Impact Report",
                "summary": summary,
                "sections": sections,
                "risk_level": risk,
                "risk_score": score,
                "confidence": confidence,
                "signals": signals,
                "impacts": _impact_for_conflict(themes),
            }

        impacts = self._filter_impacts(data.get("impacts", []), industry_filter)
        themes = []
        for row in data.get("articles", []) or []:
            themes.append(str(row.get("themes", "")))
        score, signals = _score_conflict(int(data.get("count", 0) or 0), themes)
        risk = _risk_level(score)
        confidence = _confidence_conflict(int(data.get("count", 0) or 0))
        summary = [
            f"Region: {region.name}",
            f"Articles: {data.get('count', 0)} recent signals",
            f"Risk Level: {risk} (score {score}/10)",
            f"Confidence: {confidence}",
        ]
        if industry_filter != "all":
            summary.append(f"Industry Filter: {industry_filter}")
        if signals:
            summary.append("Signals: " + " ".join(signals[:2]))
        if impacts:
            summary.append("Impacts: " + " ".join(impacts[:2]))

        sections = [
            {
                "title": "Conflict Signals (Top Articles)",
                "rows": [
                    [row.get("time", ""), row.get("title", "")[:80]]
                    for row in data.get("articles", [])
                ],
            }
        ]
        if impacts:
            sections.append({
                "title": "Industry Impact",
                "rows": [[f"- {impact}", ""] for impact in impacts],
            })
        if signals:
            sections.append({
                "title": "Conflict Signals",
                "rows": [[f"- {signal}", ""] for signal in signals],
            })
        sections.append({
            "title": "Outlook",
            "rows": [[self._conflict_outlook(risk, region, industry_filter), ""]],
        })
        sections.append({
            "title": "Model Notes",
            "rows": [[f"Confidence: {confidence} | Signals: {len(signals)} | Impacts: {len(impacts)} | Scope: {region.name} | Industry: {industry_filter}", ""]],
        })
        sources = ["GDELT"]
        news_items = news_payload.get("items", []) if news_payload else []
        if news_items:
            filtered = self._filter_news(news_items, region.name, industry_filter)
            if categories:
                filtered = _filter_conflict_news(filtered, region.name, categories=categories)
            if filtered:
                sections.append({
                    "title": "News Signals",
                    "rows": [[item.get("source", ""), item.get("title", "")[:90]] for item in filtered[:6]],
                })
        if news_items:
            sources.extend(sorted({str(item.get("source", "")) for item in news_items if item.get("source")}))
        if sources:
            sections.append({
                "title": "Report Sources",
                "rows": [[source, ""] for source in sorted(set(sources))],
            })
        return {
            "title": "Conflict Impact Report",
            "summary": summary,
            "sections": sections,
            "risk_level": risk,
            "risk_score": score,
            "confidence": confidence,
            "signals": signals,
            "impacts": impacts,
        }

    def combined_report(
        self,
        region_name: str,
        industry_filter: str = "all",
        enabled_sources: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, object]:
        weather = self.weather_report(region_name, industry_filter)
        conflict = self.conflict_report(
            region_name,
            industry_filter,
            enabled_sources=enabled_sources,
            categories=categories,
        )
        news_payload = self.fetch_news_signals(
            ttl_seconds=600,
            enabled_sources=enabled_sources,
        )
        news_filtered = []
        news_items = news_payload.get("items", []) if news_payload else []
        if news_items:
            news_filtered = self._filter_news(news_items, region_name, industry_filter)
            if categories:
                news_filtered = _filter_conflict_news(news_filtered, region_name, categories=categories)
        weather_score = weather.get("risk_score")
        conflict_score = conflict.get("risk_score")
        weather_ok = weather_score is not None
        conflict_ok = conflict_score is not None
        combined_score = None
        if weather_ok and conflict_ok:
            w_score = int(weather_score or 0)
            c_score = int(conflict_score or 0)
            combined_score = min(10, int(round((w_score + c_score) / 2 + max(w_score, c_score) / 4)))
            combined_risk = _risk_level(combined_score)
            confidence = "High"
            if "Low" in (weather.get("confidence"), conflict.get("confidence")):
                confidence = "Medium"
            if weather.get("confidence") == "Low" and conflict.get("confidence") == "Low":
                confidence = "Low"
        elif weather_ok or conflict_ok:
            score_val = int(weather_score or conflict_score or 0)
            combined_score = score_val
            combined_risk = _risk_level(score_val)
            confidence = "Low"
        else:
            combined_risk = "Unavailable"
            confidence = "Low"
        summary = [
            f"Region: {region_name}",
            "Weather: " + (weather.get("summary", ["n/a"])[-1] if weather.get("summary") else "n/a"),
            "Conflict: " + (conflict.get("summary", ["n/a"])[-1] if conflict.get("summary") else "n/a"),
            f"Combined Risk: {combined_risk}" + (f" (score {combined_score}/10)" if combined_score is not None else ""),
            f"Confidence: {confidence}",
        ]
        if not conflict_ok:
            summary.append("Conflict source unavailable (GDELT cooldown or error).")
        if not weather_ok:
            summary.append("Weather source unavailable.")
        if industry_filter != "all":
            summary.append(f"Industry Filter: {industry_filter}")
        sections = []
        fusion_signals = list(dict.fromkeys((weather.get("signals") or []) + (conflict.get("signals") or [])))
        fusion_impacts = list(dict.fromkeys((weather.get("impacts") or []) + (conflict.get("impacts") or [])))
        sections.append({
            "title": "Combined Overview",
            "rows": [
                ["Combined Risk", f"{combined_risk}" + (f" ({combined_score}/10)" if combined_score is not None else "")],
                ["Confidence", confidence],
                ["Key Signals", "; ".join(fusion_signals[:5]) or "None detected"],
                ["Key Impacts", "; ".join(fusion_impacts[:5]) or "None detected"],
            ],
        })
        if weather.get("sections"):
            sections.append({"title": "Weather Snapshot", "rows": weather["summary"]})
            sections.extend(weather["sections"])
        if conflict.get("sections"):
            sections.append({"title": "Conflict Snapshot", "rows": conflict["summary"]})
            sections.extend(conflict["sections"])
        sources = ["Open-Meteo", "GDELT"]
        if news_filtered:
            sections.append({
                "title": "News Signals",
                "rows": [[item.get("source", ""), item.get("title", "")[:90]] for item in news_filtered[:8]],
            })
        if news_items:
            sources.extend(sorted({str(item.get("source", "")) for item in news_items if item.get("source")}))
        if sources:
            sections.append({
                "title": "Report Sources",
                "rows": [[source, ""] for source in sorted(set(sources))],
            })
        return {
            "title": "Global Impact Report",
            "summary": summary,
            "sections": sections,
            "risk_level": combined_risk,
            "risk_score": combined_score,
            "confidence": confidence,
        }

    def _weather_outlook(self, risk: str, region: RegionSpec, industry_filter: str) -> str:
        if risk in ("High", "Severe"):
            return f"Expect elevated operational risk in {region.name} over the next 24h. Monitor aviation, shipping, and energy loads."
        if risk == "Moderate":
            return f"Moderate disruption risk in {region.name}. Logistics and agriculture could see delays."
        return f"Low near-term disruption risk in {region.name}."

    def _conflict_outlook(self, risk: str, region: RegionSpec, industry_filter: str) -> str:
        if risk in ("High", "Severe"):
            return f"Heightened conflict risk signals in {region.name}. Watch energy, logistics, and defense exposure."
        if risk == "Moderate":
            return f"Moderate conflict signals in {region.name}. Focus on supply chain exposure."
        return f"Low conflict signal density in {region.name}."
