import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from utils.system import SystemHost
from utils.scroll_text import build_scrolling_line


@dataclass
class TrackerPoint:
    lat: float
    lon: float
    label: str
    category: str
    kind: str
    altitude_ft: Optional[float] = None
    speed_kts: Optional[float] = None
    heading_deg: Optional[float] = None
    country: Optional[str] = None
    updated_ts: Optional[int] = None
    industry: Optional[str] = None


class TrackerProviders:
    OPENSKY_URL = "https://opensky-network.org/api/states/all"

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
    def fetch_flights(limit: int = 200) -> Tuple[List[TrackerPoint], List[str]]:
        warnings: List[str] = []
        include_commercial = os.getenv("CLEAR_INCLUDE_COMMERCIAL", "0") == "1"
        include_private = os.getenv("CLEAR_INCLUDE_PRIVATE", "0") == "1"
        username = os.getenv("OPENSKY_USERNAME")
        password = os.getenv("OPENSKY_PASSWORD")
        auth = (username, password) if username and password else None
        if not auth:
            warnings.append("Set OPENSKY_USERNAME/OPENSKY_PASSWORD for higher rate limits.")

        try:
            resp = requests.get(
                TrackerProviders.OPENSKY_URL,
                auth=auth,
                headers={"User-Agent": "clear-cli/1.0"},
                timeout=8,
            )
            if resp.status_code != 200:
                warnings.append(f"OpenSky HTTP {resp.status_code}")
                return [], warnings
            data = resp.json() or {}
        except Exception as exc:
            warnings.append(f"OpenSky fetch failed: {exc}")
            data = {}
            states = []
        else:
            states = data.get("states", []) or []

        points: List[TrackerPoint] = []
        for row in states:
            if not isinstance(row, list) or len(row) < 7:
                continue
            callsign = (row[1] or "").strip()
            lon = TrackerProviders._safe_float(row[5])
            lat = TrackerProviders._safe_float(row[6])
            if lat is None or lon is None:
                continue
            origin = row[2] if len(row) > 2 else None
            baro_alt = TrackerProviders._safe_float(row[7] if len(row) > 7 else None)
            geo_alt = TrackerProviders._safe_float(row[13] if len(row) > 13 else None)
            altitude = geo_alt if geo_alt is not None else baro_alt
            velocity = TrackerProviders._safe_float(row[9] if len(row) > 9 else None)
            heading = TrackerProviders._safe_float(row[10] if len(row) > 10 else None)
            updated = int(row[4] or 0) if len(row) > 4 and row[4] else None

            altitude_ft = altitude * 3.28084 if altitude is not None else None
            speed_kts = velocity * 1.94384 if velocity is not None else None
            category = TrackerProviders._callsign_category(callsign)
            label = callsign or (row[0] or "UNKNOWN")
            if category == "commercial" and not include_commercial:
                high_speed = speed_kts is not None and speed_kts >= 520
                high_alt = altitude_ft is not None and altitude_ft >= 38000
                if not (high_speed or high_alt):
                    continue
            if category == "private" and not include_private:
                high_speed = speed_kts is not None and speed_kts >= 520
                high_alt = altitude_ft is not None and altitude_ft >= 38000
                if not (high_speed or high_alt):
                    continue
            points.append(TrackerPoint(
                lat=lat,
                lon=lon,
                label=label,
                category=category,
                kind="flight",
                altitude_ft=altitude_ft,
                speed_kts=speed_kts,
                heading_deg=heading,
                country=origin,
                updated_ts=updated,
            ))
            if len(points) >= limit:
                break

        if not points:
            warnings.append("No live flight data returned from OpenSky.")
        return points, warnings

    @staticmethod
    def fetch_shipping(limit: int = 200) -> Tuple[List[TrackerPoint], List[str]]:
        warnings: List[str] = []
        url = os.getenv("SHIPPING_DATA_URL")
        if not url:
            warnings.append("Using demo shipping data. Set SHIPPING_DATA_URL for live vessel positions.")
            demo = [
                {"lat": 0.0, "lon": 0.0, "name": "-", "type": "cargo", "industry": None},
                {"lat": 0.0, "lon": 0.0, "name": "-", "type": "tanker", "industry": None},
                {"lat": 0.0, "lon": 0.0, "name": "-", "type": "passenger", "industry": None},
                {"lat": 0.0, "lon": 0.0, "name": "-", "type": "fishing", "industry": None},
                {"lat": 0.0, "lon": 0.0, "name": "-", "type": "military", "industry": None},
            ]
            rows = demo
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
    def __init__(self):
        self._last_refresh = 0.0
        self._cached: Dict[str, Any] = {
            "flights": [],
            "ships": [],
            "warnings": [],
        }

    def refresh(self, force: bool = False) -> Dict[str, Any]:
        now = time.time()
        if not force and (now - self._last_refresh) < 20:
            return self._cached
        flights, flight_warn = TrackerProviders.fetch_flights()
        ships, ship_warn = TrackerProviders.fetch_shipping()
        warnings = flight_warn + ship_warn
        # Preserve last good data if provider returns empty.
        if not flights and self._cached.get("flights"):
            flights = self._cached.get("flights", [])
            warnings.append("OpenSky returned empty; showing last cached flights.")
        if not ships and self._cached.get("ships"):
            ships = self._cached.get("ships", [])
            warnings.append("Shipping feed returned empty; showing last cached ships.")
        self._cached = {
            "flights": flights,
            "ships": ships,
            "warnings": warnings,
        }
        self._last_refresh = now
        return self._cached

    def get_snapshot(self, mode: str = "combined") -> Dict[str, Any]:
        data = self.refresh()
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
            payload.append({
                "kind": pt.kind,
                "category": pt.category,
                "label": pt.label,
                "lat": pt.lat,
                "lon": pt.lon,
                "altitude_ft": pt.altitude_ft,
                "speed_kts": pt.speed_kts,
                "heading_deg": pt.heading_deg,
                "country": pt.country,
                "updated_ts": pt.updated_ts,
                "industry": pt.industry,
            })

        return {
            "mode": mode,
            "count": len(payload),
            "warnings": warnings,
            "points": payload,
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
    ) -> Panel:
        snapshot = snapshot or self.get_snapshot(mode=mode)
        points = snapshot.get("points", [])
        warnings: List[str] = snapshot.get("warnings", [])
        demo_shipping = any("demo shipping" in str(w).lower() for w in warnings)

        table = Table(box=box.MINIMAL_DOUBLE_HEAD, expand=True)
        table.add_column("Type", style="bold", width=8)
        table.add_column("Category", width=10)
        table.add_column("Label", width=12)
        table.add_column("Country", width=10)
        table.add_column("Lat", justify="right", width=7)
        table.add_column("Lon", justify="right", width=8)
        table.add_column("Alt(ft)", justify="right", width=8)
        table.add_column("Spd(kts)", justify="right", width=8)
        table.add_column("Hdg", justify="right", width=5)
        table.add_column("Age", justify="right", width=5)
        table.add_column("Industry", width=10)

        sample_limit = max_rows if max_rows is not None else 60
        sample = points[:max(1, sample_limit)]
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
                "-" if hdg is None else f"{hdg:,.0f}",
                age,
                str(pt.get("industry", "") or "-")[:10],
            )

        if not sample:
            table.add_row("N/A", "N/A", "No live data", "-", "-", "-", "-", "-", "-", "-", "-")

        if warnings:
            warn_lines = list(dict.fromkeys(warnings))
            warn_lines.append(f"Flights: {len([p for p in points if p.get('kind') == 'flight'])} | Ships: {len([p for p in points if p.get('kind') == 'ship'])}")
            warn_lines.append("Last update: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._last_refresh)))
            warn_lines.append("Note: OpenSky anonymous access is rate-limited and may return empty datasets.")
            warn_lines.append("Setup: OpenSky -> OPENSKY_USERNAME/OPENSKY_PASSWORD | Shipping -> SHIPPING_DATA_URL")
            warn_text = Text("\n".join(warn_lines), style="dim")
        else:
            live_lines = [
                "Live data active.",
                "Last update: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._last_refresh)),
                "Note: OpenSky anonymous access is rate-limited and may return empty datasets.",
            ]
            warn_text = Text("\n".join(live_lines), style="green")
        warn_panel = Panel(warn_text, title="Status", border_style="dim", box=box.SQUARE)

        layout = Table.grid(expand=True)
        layout.add_column(ratio=1)
        if demo_shipping and mode in ("ships", "combined"):
            note = Text("Showing default shipping list (no live container ship feed configured).", style="yellow")
            layout.add_row(Panel(note, box=box.SQUARE, border_style="dim"))
        layout.add_row(Panel(table, title="Live Tracker Feed", box=box.ROUNDED))
        layout.add_row(warn_panel)

        title = "Global Trackers"
        mode_label = "Flights + Shipping" if mode == "combined" else mode.title()
        filter_text = filter_label or "All"
        count_text = f"{len(points)} rows"
        subtitle = Text.assemble(
            ("Mode: ", "dim"),
            (mode_label, "bold cyan"),
            ("  |  Filter: ", "dim"),
            (filter_text, "bold magenta"),
            ("  |  ", "dim"),
            (count_text, "bold white"),
        )
        return Panel(Group(layout), title=title, subtitle=subtitle, box=box.DOUBLE, border_style="cyan")
