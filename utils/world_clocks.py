from datetime import datetime
from typing import List, Optional, Tuple

from rich.table import Table
from rich.panel import Panel
from rich import box

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

CLOCK_CITIES: List[Tuple[str, Optional[str]]] = [
    ("Local", None),
    ("UTC", "UTC"),
    ("Honolulu", "Pacific/Honolulu"),
    ("Anchorage", "America/Anchorage"), 
    ("Los Angeles", "America/Los_Angeles"),
    ("Denver", "America/Denver"),
    ("Chicago", "America/Chicago"),
    ("New York", "America/New_York"),
    ("Caracas", "America/Caracas"),
    ("Rio de Janeiro", "America/Sao_Paulo"),
    ("London", "Europe/London"),
    ("Berlin", "Europe/Berlin"),
    ("Moscow", "Europe/Moscow"),
    ("Dubai", "Asia/Dubai"),
    ("Kabul", "Asia/Kabul"),
    ("Mumbai", "Asia/Kolkata"),
    ("Beijing", "Asia/Shanghai"),
    ("Tokyo", "Asia/Tokyo"),
    ("Sydney", "Australia/Sydney"),
]


def _localized_time(tzname: Optional[str]) -> str:
    try:
        if tzname and ZoneInfo:
            now = datetime.now(ZoneInfo(tzname))
        else:
            now = datetime.now()
        return now.strftime("%Y-%m-%d • %H:%M")
    except Exception:
        return "N/A"


def build_world_clocks_panel(width: Optional[int] = None) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column("City", style="bold cyan")
    table.add_column("Time", style="white")
    for city, tz in CLOCK_CITIES:
        table.add_row(city, _localized_time(tz))

    panel_width = min(max(24, width or 60), 70)
    return Panel(
        table,
        box=box.ROUNDED,
        border_style="blue",
        width=panel_width,
    )
