import json
import os
import time
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

import requests
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from utils.system import SystemHost
from utils.scroll_text import build_scrolling_line
from utils.charts import ChartRenderer
from modules.market_data.flight_registry import get_operator_info


@dataclass
class TrackerPoint:
    lat: float
    lon: float
    label: str
    category: str
    kind: str
    icao24: Optional[str] = None
    callsign: Optional[str] = None
    operator: Optional[str] = None
    flight_number: Optional[str] = None
    tail_number: Optional[str] = None
    altitude_ft: Optional[float] = None
    speed_kts: Optional[float] = None
    heading_deg: Optional[float] = None
    country: Optional[str] = None
    updated_ts: Optional[int] = None
    industry: Optional[str] = None


class TrackerProviders:
    _LAT_KEYS = ("lat", "latitude", "latitude_deg", "lat_deg")
    _LON_KEYS = ("lon", "lng", "longitude", "longitude_deg", "lon_deg")
    _CALLSIGN_KEYS = ("callsign", "flight", "flight_iata", "flight_icao", "label")
    _ICAO_KEYS = ("icao24", "hex", "icao")
    _OPERATOR_KEYS = ("operator", "airline_iata", "airline_icao", "airline")
    _FLIGHT_NUM_KEYS = ("flight_number", "flight_iata", "flight_icao", "flight")
    _TAIL_KEYS = ("tail_number", "registration", "reg")
    _ALT_KEYS = ("altitude_ft", "alt_ft", "altitude", "alt")
    _SPEED_KEYS = ("speed_kts", "speed", "velocity")
    _HEADING_KEYS = ("heading_deg", "heading", "track", "bearing")
    _COUNTRY_KEYS = ("country", "origin")
    _CATEGORY_KEYS = ("category", "type", "flight_type")
    _OPENSKY_URL = "https://opensky-network.org/api/states/all"

    @staticmethod
    def _parse_sources(env_value: Optional[str]) -> List[str]:
        if not env_value:
            return []
        return [item.strip() for item in env_value.split(",") if item.strip()]

    @staticmethod
    def _first_value(row: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
        for key in keys:
            if key in row and row.get(key) not in (None, ""):
                return row.get(key)
        return None

    @staticmethod
    def _extract_rows(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("data", "flights", "aircraft", "states", "items"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
        return []

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _callsign_category(callsign: str) -> str:
        cs = (callsign or "").strip().upper()
        if not cs:
            return "unknown"
        military_keys = ("RCH", "MC", "NAVY", "AF", "ARMY", "MIL", "QID")
        cargo_keys = ("FDX", "UPS", "GTI", "CARGO", "BOX", "ABW")
        gov_keys = ("GOV", "STATE", "NASA")
        vip_keys = ("AF1", "SAM", "SPAR", "VIP", "EXEC")
        private_keys = ("N", "G-", "D-", "C-")
        if any(k in cs for k in military_keys):
            return "military"
        if any(k in cs for k in gov_keys):
            return "government"
        if any(k in cs for k in vip_keys):
            return "vip"
        if any(k in cs for k in cargo_keys):
            return "cargo"
        if cs.startswith(private_keys) and len(cs) <= 6:
            return "private"
        return "commercial"

    @staticmethod
    def _parse_flight_identity(callsign: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        cs = (callsign or "").strip().upper()
        if not cs:
            return None, None, None
        operator = None
        flight_number = None
        tail_number = None
        if len(cs) >= 3 and cs[:3].isalpha():
            operator = cs[:3]
            flight_number = cs[3:] if cs[3:].isdigit() else cs[3:]
        tail_prefixes = ("N", "G-", "D-", "C-", "VH-", "ZS-", "F-", "I-", "JA")
        if cs.startswith(tail_prefixes):
            tail_number = cs
        return operator, flight_number, tail_number

    @staticmethod
    def fetch_flights(limit: int = 200) -> Tuple[List[TrackerPoint], List[str]]:
        warnings: List[str] = []
        include_commercial = os.getenv("CLEAR_INCLUDE_COMMERCIAL", "0") == "1"
        include_private = os.getenv("CLEAR_INCLUDE_PRIVATE", "0") == "1"
        urls = TrackerProviders._parse_sources(os.getenv("FLIGHT_DATA_URL"))
        data_paths = TrackerProviders._parse_sources(os.getenv("FLIGHT_DATA_PATH"))
        rows_by_source: List[Tuple[List[Dict[str, Any]], str]] = []
        use_opensky = False
        if not urls and not data_paths:
            use_opensky = True

        for data_path in data_paths:
            try:
                with open(data_path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                rows = TrackerProviders._extract_rows(payload)
                if not rows:
                    warnings.append(f"Flight feed empty: {data_path}")
                rows_by_source.append((rows, data_path))
            except Exception as exc:
                warnings.append(f"Flight feed file failed: {data_path}: {exc}")
        for url in urls:
            try:
                resp = requests.get(url, timeout=8)
                if resp.status_code != 200:
                    warnings.append(f"Flight feed HTTP {resp.status_code} ({url})")
                    continue
                payload = resp.json()
                rows = TrackerProviders._extract_rows(payload)
                if not rows:
                    warnings.append(f"Flight feed empty: {url}")
                rows_by_source.append((rows, url))
            except Exception as exc:
                warnings.append(f"Flight feed fetch failed: {url}: {exc}")

        if use_opensky:
            opensky_rows, opensky_warnings = TrackerProviders._fetch_opensky_rows()
            warnings.extend(opensky_warnings)
            if opensky_rows:
                rows_by_source.append((opensky_rows, "opensky"))

        points: List[TrackerPoint] = []
        for rows, source in rows_by_source:
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                lat = TrackerProviders._safe_float(
                    TrackerProviders._first_value(row, TrackerProviders._LAT_KEYS)
                )
                lon = TrackerProviders._safe_float(
                    TrackerProviders._first_value(row, TrackerProviders._LON_KEYS)
                )
                if lat is None or lon is None:
                    continue
                callsign_raw = TrackerProviders._first_value(row, TrackerProviders._CALLSIGN_KEYS)
                icao_raw = TrackerProviders._first_value(row, TrackerProviders._ICAO_KEYS)
                callsign = str(callsign_raw or "").strip()
                label = callsign or str(row.get("label") or icao_raw or "UNKNOWN")
                icao24 = str(icao_raw or "").strip().upper() or None
                altitude_ft = TrackerProviders._safe_float(
                    TrackerProviders._first_value(row, TrackerProviders._ALT_KEYS)
                )
                speed_kts = TrackerProviders._safe_float(
                    TrackerProviders._first_value(row, TrackerProviders._SPEED_KEYS)
                )
                heading = TrackerProviders._safe_float(
                    TrackerProviders._first_value(row, TrackerProviders._HEADING_KEYS)
                )
                updated = row.get("updated_ts") or row.get("timestamp")
                try:
                    updated_ts = int(updated) if updated is not None else None
                except Exception:
                    updated_ts = None
                category_value = TrackerProviders._first_value(row, TrackerProviders._CATEGORY_KEYS)
                category = str(category_value or TrackerProviders._callsign_category(callsign)).lower()
                operator = TrackerProviders._first_value(row, TrackerProviders._OPERATOR_KEYS)
                flight_number = TrackerProviders._first_value(row, TrackerProviders._FLIGHT_NUM_KEYS)
                tail_number = TrackerProviders._first_value(row, TrackerProviders._TAIL_KEYS)
                if operator is None or flight_number is None or tail_number is None:
                    op_guess, flight_guess, tail_guess = TrackerProviders._parse_flight_identity(callsign)
                    operator = operator or op_guess
                    flight_number = flight_number or flight_guess
                    tail_number = tail_number or tail_guess
                if category == "commercial" and not include_commercial:
                    high_speed = speed_kts is not None and speed_kts >= 520
                    high_alt = altitude_ft is not None and altitude_ft >= 38000
                    if (speed_kts is not None or altitude_ft is not None) and not (high_speed or high_alt):
                        continue
                if category == "private" and not include_private:
                    high_speed = speed_kts is not None and speed_kts >= 520
                    high_alt = altitude_ft is not None and altitude_ft >= 38000
                    if (speed_kts is not None or altitude_ft is not None) and not (high_speed or high_alt):
                        continue
                points.append(TrackerPoint(
                    lat=lat,
                    lon=lon,
                    label=label,
                    category=category or "unknown",
                    kind="flight",
                    icao24=icao24,
                    callsign=callsign or None,
                    operator=str(operator).strip() if operator is not None else None,
                    flight_number=str(flight_number).strip() if flight_number is not None else None,
                    tail_number=str(tail_number).strip() if tail_number is not None else None,
                    altitude_ft=altitude_ft,
                    speed_kts=speed_kts,
                    heading_deg=heading,
                    country=str(TrackerProviders._first_value(row, TrackerProviders._COUNTRY_KEYS) or "").strip() or None,
                    updated_ts=updated_ts,
                ))
                if len(points) >= limit:
                    break
            if len(points) >= limit:
                break

        if not points:
            if use_opensky:
                warnings.append("No live flight data returned from OpenSky.")
            else:
                warnings.append("No live flight data returned from the flight feed.")
        return points, warnings

    @staticmethod
    def _fetch_opensky_rows() -> Tuple[List[Dict[str, Any]], List[str]]:
        warnings: List[str] = []
        username = os.getenv("OPENSKY_USERNAME")
        password = os.getenv("OPENSKY_PASSWORD")
        auth = (username, password) if username and password else None
        try:
            resp = requests.get(TrackerProviders._OPENSKY_URL, timeout=8, auth=auth)
            if resp.status_code != 200:
                warnings.append(f"OpenSky HTTP {resp.status_code}")
                return [], warnings
            payload = resp.json()
        except Exception as exc:
            warnings.append(f"OpenSky fetch failed: {exc}")
            return [], warnings
        states = payload.get("states") if isinstance(payload, dict) else None
        if not states:
            warnings.append("OpenSky returned empty data.")
            return [], warnings
        rows = []
        for state in states:
            if not isinstance(state, list) or len(state) < 7:
                continue
            lon = state[5]
            lat = state[6]
            if lat is None or lon is None:
                continue
            callsign = (state[1] or "").strip()
            velocity = state[9]
            heading = state[10]
            geo_alt = state[13]
            updated = state[4] or state[3]
            rows.append({
                "lat": lat,
                "lon": lon,
                "callsign": callsign,
                "icao24": state[0],
                "country": state[2],
                "speed_kts": (float(velocity) * 1.94384) if velocity is not None else None,
                "heading_deg": float(heading) if heading is not None else None,
                "altitude_ft": (float(geo_alt) * 3.28084) if geo_alt is not None else None,
                "updated_ts": int(updated) if updated is not None else None,
            })
        return rows, warnings

    @staticmethod
    def fetch_shipping(limit: int = 200) -> Tuple[List[TrackerPoint], List[str]]:
        warnings: List[str] = []
        url = os.getenv("SHIPPING_DATA_URL")
        if not url:
            warnings.append("No vessel feed configured.")
            return [], warnings
        else:
            rows = None

        try:
            if rows is None:
                resp = requests.get(url, timeout=8)
                if resp.status_code != 200:
                    warnings.append(f"Shipping HTTP {resp.status_code}")
                    return [], warnings
                payload = resp.json()
                rows = payload if isinstance(payload, list) else payload.get("data", [])
        except Exception as exc:
            warnings.append(f"Shipping fetch failed: {exc}")
            return [], warnings

        points: List[TrackerPoint] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            lat = TrackerProviders._safe_float(row.get("lat"))
            lon = TrackerProviders._safe_float(row.get("lon"))
            if lat is None or lon is None:
                continue
            label = str(row.get("name") or row.get("mmsi") or "VESSEL")
            raw_type = str(row.get("type") or row.get("category") or "").lower()
            industry = str(row.get("industry") or row.get("cargo") or row.get("cargo_type") or "").strip()
            speed = TrackerProviders._safe_float(row.get("speed"))
            heading = TrackerProviders._safe_float(row.get("heading") or row.get("course"))
            updated = None
            if row.get("timestamp"):
                try:
                    updated = int(float(row.get("timestamp")))
                except Exception:
                    updated = None
            if "gov" in raw_type or "state" in raw_type:
                category = "government"
            elif "mil" in raw_type:
                category = "military"
            elif "tanker" in raw_type:
                category = "tanker"
            elif "cargo" in raw_type or "freight" in raw_type:
                category = "cargo"
            elif "passenger" in raw_type or "cruise" in raw_type:
                category = "passenger"
            elif "fish" in raw_type:
                category = "fishing"
            elif "pleasure" in raw_type or "yacht" in raw_type:
                category = "pleasure"
            else:
                category = "unknown"
            points.append(TrackerPoint(
                lat=lat,
                lon=lon,
                label=label,
                category=category,
                kind="ship",
                speed_kts=speed,
                heading_deg=heading,
                updated_ts=updated,
                industry=industry or None,
            ))
            if len(points) >= limit:
                break

        return points, warnings


class TrackerHealth:
    @staticmethod
    def perf_profile() -> str:
        info = SystemHost.get_info() or {}
        if not info.get("psutil_available"):
            return "low"
        cpu_text = str(info.get("cpu_usage", "0"))
        mem_text = str(info.get("mem_usage", "0"))
        try:
            cpu_pct = float(cpu_text.replace("%", "").strip())
        except Exception:
            cpu_pct = 0.0
        try:
            mem_pct = float(mem_text.split("%")[0])
        except Exception:
            mem_pct = 0.0
        if cpu_pct >= 75 or mem_pct >= 80:
            return "low"
        if cpu_pct >= 50 or mem_pct >= 65:
            return "medium"
        return "high"


class GlobalTrackers:
    _GLOBAL_STATE = {
        "last_refresh": 0.0,
        "cached": {
            "flights": [],
            "ships": [],
            "warnings": [],
        },
        "history": {},
        "path_history": {},
        "id_index": {},
        "route_cache": {},
        "last_seen": {},
    }
    _HISTORY_WINDOW_SEC = 900
    _HISTORY_MIN_POINTS = 4
    _SPEED_CAPS = {"flight": 650.0, "ship": 40.0}
    _VOL_CAPS = {"flight": 100.0, "ship": 12.0}

    def __init__(self):
        self._state = GlobalTrackers._GLOBAL_STATE
        self._last_refresh = float(self._state.get("last_refresh", 0.0) or 0.0)
        self._cached = self._state.get("cached", {
            "flights": [],
            "ships": [],
            "warnings": [],
        })
        self._history = self._state.get("history", {})
        self._path_history = self._state.get("path_history", {})
        self._id_index = self._state.get("id_index", {})
        self._route_cache = self._state.get("route_cache", {})
        self._last_seen = self._state.get("last_seen", {})

    def _sync_state(self) -> None:
        self._state["cached"] = self._cached
        self._state["last_refresh"] = self._last_refresh
        self._state["history"] = self._history
        self._state["path_history"] = self._path_history
        self._state["id_index"] = self._id_index
        self._state["route_cache"] = self._route_cache
        self._state["last_seen"] = self._last_seen

    @staticmethod
    def _point_id(point: TrackerPoint) -> str:
        label = (point.label or "unknown").strip().upper()
        country = (point.country or "").strip().upper()
        category = (point.category or "").strip().lower()
        return f"{point.kind}:{label}:{country}:{category}"

    @staticmethod
    def _stddev(values: List[float]) -> Optional[float]:
        if len(values) < GlobalTrackers._HISTORY_MIN_POINTS:
            return None
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance)

    @staticmethod
    def _heat_from_value(value: Optional[float], cap: float) -> Optional[float]:
        if value is None:
            return None
        if cap <= 0:
            return 0.0
        return max(0.0, min(float(value) / cap, 1.0))

    def _update_history(self, points: List[TrackerPoint]) -> None:
        now = int(time.time())
        window = self._HISTORY_WINDOW_SEC
        for pt in points:
            if pt.speed_kts is None:
                speed = None
            else:
                speed = float(pt.speed_kts)
            key = self._point_id(pt)
            self._last_seen[key] = now
            if key not in self._history:
                self._history[key] = deque()
            series: Deque[Tuple[int, float]] = self._history[key]
            ts = int(pt.updated_ts or now)
            if speed is not None:
                series.append((ts, speed))
            while series and (now - series[0][0]) > window:
                series.popleft()
            if key not in self._path_history:
                self._path_history[key] = deque()
            path_series: Deque[Tuple[int, float, float, Optional[float], Optional[float], Optional[float]]] = self._path_history[key]
            path_series.append((ts, float(pt.lat), float(pt.lon), pt.speed_kts, pt.altitude_ft, pt.heading_deg))
            while path_series and (now - path_series[0][0]) > window:
                path_series.popleft()

        stale_cutoff = now - (window * 2)
        stale_keys = [k for k, last in self._last_seen.items() if last < stale_cutoff]
        for key in stale_keys:
            self._last_seen.pop(key, None)
            self._history.pop(key, None)
            self._path_history.pop(key, None)

    def _point_metrics(self, point: TrackerPoint) -> Dict[str, Optional[float]]:
        key = self._point_id(point)
        series = self._history.get(key)
        speeds = [value for _, value in series] if series else []
        volatility = self._stddev(speeds) if speeds else None
        speed_cap = self._SPEED_CAPS.get(point.kind, 100.0)
        vol_cap = self._VOL_CAPS.get(point.kind, 20.0)
        speed_heat = self._heat_from_value(point.speed_kts, speed_cap)
        vol_heat = self._heat_from_value(volatility, vol_cap)
        return {
            "speed_heat": speed_heat,
            "speed_vol_kts": volatility,
            "vol_heat": vol_heat,
        }

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius_km = 6371.0
        lat1_r = math.radians(lat1)
        lon1_r = math.radians(lon1)
        lat2_r = math.radians(lat2)
        lon2_r = math.radians(lon2)
        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius_km * c

    @staticmethod
    def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        dlon = math.radians(lon2 - lon1)
        x = math.sin(dlon) * math.cos(lat2_r)
        y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon)
        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360

    @staticmethod
    def _direction_label(bearing: Optional[float]) -> str:
        if bearing is None:
            return "Unknown"
        directions = [
            (22.5, "N"),
            (67.5, "NE"),
            (112.5, "E"),
            (157.5, "SE"),
            (202.5, "S"),
            (247.5, "SW"),
            (292.5, "W"),
            (337.5, "NW"),
            (360.0, "N"),
        ]
        for cutoff, label in directions:
            if bearing < cutoff:
                return label
        return "N"

    @staticmethod
    def _normalize_query(text: Optional[str]) -> str:
        return (text or "").strip().lower()

    def _match_query(self, value: Optional[str], query: str) -> bool:
        if not value:
            return False
        return query in value.lower()

    @staticmethod
    def _string_or_unknown(value: Optional[str]) -> str:
        if value is None:
            return "unknown"
        cleaned = str(value).strip()
        return cleaned if cleaned else "unknown"

    def refresh(self, force: bool = False) -> Dict[str, Any]:
        self._last_refresh = float(self._state.get("last_refresh", 0.0) or 0.0)
        self._cached = self._state.get("cached", self._cached)
        self._history = self._state.get("history", self._history)
        self._last_seen = self._state.get("last_seen", self._last_seen)
        now = time.time()
        if not force and (now - self._last_refresh) < 20:
            return self._cached
        flights, flight_warn = TrackerProviders.fetch_flights()
        ships, ship_warn = TrackerProviders.fetch_shipping()
        warnings = flight_warn + ship_warn
        # Preserve last good data if provider returns empty.
        if not flights and self._cached.get("flights"):
            flights = self._cached.get("flights", [])
            warnings.append("Flight feed returned empty; showing last cached flights.")
        if not ships and self._cached.get("ships"):
            ships = self._cached.get("ships", [])
            warnings.append("Shipping feed returned empty; showing last cached ships.")
        self._update_history(flights + ships)
        self._cached = {
            "flights": flights,
            "ships": ships,
            "warnings": warnings,
        }
        self._last_refresh = now
        self._sync_state()
        return self._cached

    def get_snapshot(self, mode: str = "combined", allow_refresh: bool = True) -> Dict[str, Any]:
        self._last_refresh = float(self._state.get("last_refresh", 0.0) or 0.0)
        self._cached = self._state.get("cached", self._cached)
        self._history = self._state.get("history", self._history)
        self._path_history = self._state.get("path_history", self._path_history)
        self._id_index = self._state.get("id_index", self._id_index)
        self._route_cache = self._state.get("route_cache", self._route_cache)
        self._last_seen = self._state.get("last_seen", self._last_seen)
        data = self.refresh() if allow_refresh else self._cached
        flights: List[TrackerPoint] = data.get("flights", [])
        ships: List[TrackerPoint] = data.get("ships", [])
        warnings: List[str] = data.get("warnings", [])

        if mode == "flights":
            points = flights
        elif mode == "ships":
            points = ships
        else:
            points = flights + ships

        payload = []
        for pt in points:
            metrics = self._point_metrics(pt)
            point_id = self._point_id(pt)
            tracker_id = pt.icao24 or point_id
            self._id_index[str(tracker_id).lower()] = point_id
            operator_info = get_operator_info(pt.operator)
            payload.append({
                "id": tracker_id,
                "kind": pt.kind,
                "category": pt.category,
                "label": pt.label,
                "icao24": self._string_or_unknown(pt.icao24),
                "callsign": self._string_or_unknown(pt.callsign),
                "operator": self._string_or_unknown(pt.operator),
                "operator_name": operator_info.get("name"),
                "operator_country": operator_info.get("country"),
                "flight_number": self._string_or_unknown(pt.flight_number),
                "tail_number": self._string_or_unknown(pt.tail_number),
                "lat": pt.lat,
                "lon": pt.lon,
                "altitude_ft": pt.altitude_ft,
                "speed_kts": pt.speed_kts,
                "heading_deg": pt.heading_deg,
                "country": self._string_or_unknown(pt.country),
                "updated_ts": pt.updated_ts,
                "industry": self._string_or_unknown(pt.industry),
                "speed_heat": metrics.get("speed_heat"),
                "speed_vol_kts": metrics.get("speed_vol_kts"),
                "vol_heat": metrics.get("vol_heat"),
            })

        self._sync_state()
        return {
            "mode": mode,
            "count": len(payload),
            "warnings": warnings,
            "points": payload,
        }

    def search_snapshot(
        self,
        snapshot: Dict[str, Any],
        query: str,
        fields: Optional[List[str]] = None,
        kind: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        query_norm = self._normalize_query(query)
        if not query_norm:
            return {"query": query, "count": 0, "points": []}
        allowed_fields = {
            "label",
            "category",
            "country",
            "icao24",
            "callsign",
            "operator",
            "flight_number",
            "tail_number",
        }
        if fields:
            search_fields = [f for f in fields if f in allowed_fields]
            if not search_fields:
                search_fields = list(allowed_fields)
        else:
            search_fields = list(allowed_fields)
        points = snapshot.get("points", [])
        results = []
        for pt in points:
            if kind and str(pt.get("kind", "")).lower() != kind.lower():
                continue
            for field in search_fields:
                if self._match_query(str(pt.get(field) or ""), query_norm):
                    results.append(pt)
                    break
            if len(results) >= limit:
                break
        return {"query": query, "count": len(results), "points": results}

    def get_history(self, tracker_id: str) -> Dict[str, Any]:
        if not tracker_id:
            return {"id": tracker_id, "history": []}
        tracker_key = self._id_index.get(tracker_id.lower())
        if not tracker_key:
            tracker_key = self._id_index.get(tracker_id.strip().lower())
        if not tracker_key:
            return {"id": tracker_id, "history": []}
        series = self._path_history.get(tracker_key, [])
        history = [
            {
                "ts": ts,
                "lat": lat,
                "lon": lon,
                "speed_kts": speed,
                "altitude_ft": altitude,
                "heading_deg": heading,
            }
            for ts, lat, lon, speed, altitude, heading in series
        ]
        summary: Dict[str, Any] = {"points": len(history)}
        cache_key = None
        if series:
            cache_key = f"{tracker_key}:{series[-1][0]}:{len(series)}"
            cached = self._route_cache.get(cache_key)
            if cached:
                return {"id": tracker_id, "history": history, "summary": cached}
        if len(history) >= 2:
            start = history[0]
            end = history[-1]
            distance_km = self._haversine_km(start["lat"], start["lon"], end["lat"], end["lon"])
            bearing = self._bearing_deg(start["lat"], start["lon"], end["lat"], end["lon"])
            speeds = [float(pt["speed_kts"]) for pt in history if pt.get("speed_kts") is not None]
            altitudes = [float(pt["altitude_ft"]) for pt in history if pt.get("altitude_ft") is not None]
            avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else None
            avg_alt = round(sum(altitudes) / len(altitudes), 1) if altitudes else None
            duration = max(0, int(end["ts"]) - int(start["ts"])) if end.get("ts") and start.get("ts") else None
            summary.update(
                {
                    "start": {"lat": start["lat"], "lon": start["lon"], "ts": start["ts"]},
                    "end": {"lat": end["lat"], "lon": end["lon"], "ts": end["ts"]},
                    "distance_km": round(distance_km, 2),
                    "bearing_deg": round(bearing, 1),
                    "direction": self._direction_label(bearing),
                    "avg_speed_kts": avg_speed,
                    "avg_altitude_ft": avg_alt,
                    "duration_sec": duration,
                    "route_hint": f"{round(start['lat'], 2)},{round(start['lon'], 2)} -> {round(end['lat'], 2)},{round(end['lon'], 2)}",
                }
            )
        if cache_key:
            self._route_cache[cache_key] = summary
            self._sync_state()
        return {"id": tracker_id, "history": history, "summary": summary}

    def get_detail(self, tracker_id: str, allow_refresh: bool = False) -> Dict[str, Any]:
        snapshot = self.get_snapshot(mode="combined", allow_refresh=allow_refresh)
        points = snapshot.get("points", [])
        target = None
        for pt in points:
            if str(pt.get("id", "")).lower() == tracker_id.lower():
                target = pt
                break
        history = self.get_history(tracker_id)
        return {
            "id": tracker_id,
            "point": target,
            "history": history.get("history", []),
            "summary": history.get("summary", {}),
        }

    @staticmethod
    def apply_category_filter(snapshot: Dict[str, Any], category: Optional[str]) -> Dict[str, Any]:
        if not category or str(category).lower() == "all":
            return snapshot
        wanted = str(category).lower()
        filtered = [pt for pt in snapshot.get("points", []) if str(pt.get("category", "")).lower() == wanted]
        return {
            **snapshot,
            "count": len(filtered),
            "points": filtered,
        }

    def render(
        self,
        mode: str = "combined",
        snapshot: Optional[Dict[str, Any]] = None,
        filter_label: Optional[str] = None,
        max_rows: Optional[int] = None,
        row_offset: int = 0,
    ) -> Panel:
        snapshot = snapshot or self.get_snapshot(mode=mode)
        points = snapshot.get("points", [])
        warnings: List[str] = snapshot.get("warnings", [])
        no_shipping = any("no vessel feed" in str(w).lower() for w in warnings)

        table = Table(box=box.MINIMAL_DOUBLE_HEAD, expand=True)
        table.add_column("Type", style="bold", width=8)
        table.add_column("Category", width=10)
        table.add_column("Label", width=12)
        table.add_column("Country", width=10)
        table.add_column("Lat", justify="right", width=7)
        table.add_column("Lon", justify="right", width=8)
        table.add_column("Alt(ft)", justify="right", width=8)
        table.add_column("Spd(kts)", justify="right", width=8)
        table.add_column("Spd Heat", justify="center", width=6)
        table.add_column("Vol(kts)", justify="right", width=8)
        table.add_column("Vol Heat", justify="center", width=6)
        table.add_column("Hdg", justify="right", width=5)
        table.add_column("Age", justify="right", width=5)
        table.add_column("Industry", width=10)

        sample_limit = max_rows if max_rows is not None else 60
        sample, clamped_offset, total_rows = self._slice_points(
            points,
            row_offset,
            max(1, sample_limit),
        )
        now = int(time.time())
        color_map = {
            "flight": {
                "commercial": "green",
                "cargo": "yellow",
                "private": "cyan",
                "military": "red",
                "government": "magenta",
                "unknown": "dim",
            },
            "ship": {
                "cargo": "yellow",
                "tanker": "magenta",
                "passenger": "green",
                "military": "red",
                "fishing": "cyan",
                "pleasure": "blue",
                "government": "magenta",
                "unknown": "dim",
            },
        }
        for pt in sample:
            alt = pt.get("altitude_ft")
            spd = pt.get("speed_kts")
            hdg = pt.get("heading_deg")
            cat = str(pt.get("category", "n/a"))
            kind = str(pt.get("kind", "n/a"))
            style = color_map.get(kind, {}).get(cat, None)
            speed_heat = pt.get("speed_heat")
            vol_heat = pt.get("vol_heat")
            speed_bar = ChartRenderer.generate_heatmap_bar(speed_heat, width=6) if speed_heat is not None else "-"
            vol_bar = ChartRenderer.generate_heatmap_bar(vol_heat, width=6) if vol_heat is not None else "-"
            vol_kts = pt.get("speed_vol_kts")
            age = "-"
            updated = pt.get("updated_ts")
            if updated:
                try:
                    age = str(max(0, now - int(updated)))
                except Exception:
                    age = "-"
            country = str(pt.get("country", "") or "-")[:10]
            table.add_row(
                kind,
                Text(cat, style=style) if style else cat,
                str(pt.get("label", "n/a"))[:12],
                country,
                f"{pt.get('lat', 0.0):.2f}",
                f"{pt.get('lon', 0.0):.2f}",
                "-" if alt is None else f"{alt:,.0f}",
                "-" if spd is None else f"{spd:,.0f}",
                speed_bar,
                "-" if vol_kts is None else f"{float(vol_kts):,.0f}",
                vol_bar,
                "-" if hdg is None else f"{hdg:,.0f}",
                age,
                str(pt.get("industry", "") or "-")[:10],
            )

        if not sample:
            table.add_row("N/A", "N/A", "No live data", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-")

        if warnings:
            warn_lines = list(dict.fromkeys(warnings))
            warn_lines.append(f"Flights: {len([p for p in points if p.get('kind') == 'flight'])} | Ships: {len([p for p in points if p.get('kind') == 'ship'])}")
            warn_lines.append("Last update: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._last_refresh)))
            warn_text = Text("\n".join(warn_lines), style="dim")
        else:
            live_lines = [
                "Live data active.",
                "Last update: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._last_refresh)),
            ]
            warn_text = Text("\n".join(live_lines), style="green")
        warn_panel = Panel(warn_text, title="Status", border_style="dim", box=box.SQUARE)

        layout = Table.grid(expand=True)
        layout.add_column(ratio=1)
        if no_shipping and mode in ("ships", "combined"):
            note = Text("No vessel feed configured.", style="yellow")
            layout.add_row(Panel(note, box=box.SQUARE, border_style="dim"))
        layout.add_row(Panel(table, title="Live Tracker Feed", box=box.ROUNDED))
        layout.add_row(warn_panel)

        title = "Global Trackers"
        mode_label = "Flights + Shipping" if mode == "combined" else mode.title()
        filter_text = filter_label or "All"
        if total_rows:
            start = clamped_offset + 1
            end = clamped_offset + len(sample)
            count_text = f"Rows {start}-{end} of {total_rows}"
        else:
            count_text = "0 rows"
        subtitle = Text.assemble(
            ("Mode: ", "dim"),
            (mode_label, "bold cyan"),
            ("  |  Filter: ", "dim"),
            (filter_text, "bold magenta"),
            ("  |  ", "dim"),
            (count_text, "bold white"),
        )
        return Panel(Group(layout), title=title, subtitle=subtitle, box=box.DOUBLE, border_style="cyan")

    @staticmethod
    def _slice_points(
        points: List[Dict[str, Any]],
        offset: int,
        limit: int,
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        total = len(points)
        if total == 0:
            return [], 0, 0
        if limit <= 0:
            return [], 0, total
        max_offset = max(0, total - limit)
        clamped = max(0, min(int(offset or 0), max_offset))
        return points[clamped:clamped + limit], clamped, total


class TrackerRelevance:
    TAG_RULES = {
        "shipping": {"kinds": {"ship"}, "categories": set()},
        "logistics": {"kinds": {"ship", "flight"}, "categories": set()},
        "freight": {"kinds": {"ship", "flight"}, "categories": {"cargo", "tanker"}},
        "cargo": {"kinds": {"ship", "flight"}, "categories": {"cargo", "tanker"}},
        "aviation": {"kinds": {"flight"}, "categories": set()},
        "airline": {"kinds": {"flight"}, "categories": set()},
        "defense": {"kinds": {"flight", "ship"}, "categories": {"military", "government"}},
        "military": {"kinds": {"flight", "ship"}, "categories": {"military", "government"}},
        "energy": {"kinds": {"ship"}, "categories": {"tanker"}},
        "tanker": {"kinds": {"ship"}, "categories": {"tanker"}},
        "ports": {"kinds": {"ship"}, "categories": set()},
    }

    @staticmethod
    def normalize_tag(tag: str) -> str:
        return (tag or "").strip().lower()

    @classmethod
    def match_rules(cls, account_tags: Dict[str, List[str]]) -> Tuple[List[Dict[str, set]], Dict[str, List[str]]]:
        rules = []
        matched_accounts: Dict[str, List[str]] = {}
        for account, tags in (account_tags or {}).items():
            for raw in tags or []:
                tag = cls.normalize_tag(raw)
                rule = cls.TAG_RULES.get(tag)
                if not rule:
                    continue
                rules.append(rule)
                matched_accounts.setdefault(account, [])
                if tag not in matched_accounts[account]:
                    matched_accounts[account].append(tag)
        return rules, matched_accounts

    @staticmethod
    def filter_points(points: List[Dict[str, Any]], rules: List[Dict[str, set]]) -> List[Dict[str, Any]]:
        if not rules:
            return []
        filtered = []
        for pt in points:
            kind = str(pt.get("kind", "")).lower()
            category = str(pt.get("category", "")).lower()
            for rule in rules:
                kinds = rule.get("kinds", set())
                categories = rule.get("categories", set())
                if kind not in kinds:
                    continue
                if categories and category not in categories:
                    continue
                filtered.append(pt)
                break
        return filtered

    @staticmethod
    def summarize(points: List[Dict[str, Any]]) -> Dict[str, Any]:
        def _avg(values: List[float]) -> Optional[float]:
            return (sum(values) / len(values)) if values else None

        speeds = [float(p.get("speed_kts")) for p in points if p.get("speed_kts") is not None]
        vol = [float(p.get("speed_vol_kts")) for p in points if p.get("speed_vol_kts") is not None]
        speed_heat = [float(p.get("speed_heat")) for p in points if p.get("speed_heat") is not None]
        vol_heat = [float(p.get("vol_heat")) for p in points if p.get("vol_heat") is not None]
        return {
            "point_count": len(points),
            "avg_speed_kts": _avg(speeds),
            "avg_vol_kts": _avg(vol),
            "avg_speed_heat": _avg(speed_heat),
            "avg_vol_heat": _avg(vol_heat),
            "max_speed_kts": max(speeds) if speeds else None,
            "max_vol_kts": max(vol) if vol else None,
        }
