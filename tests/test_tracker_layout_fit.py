from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from interfaces.menu_layout import build_sidebar, build_status_header
from modules.market_data.feed import MarketFeed
from utils.layout import fit_renderable_to_height


def _build_snapshot(count: int) -> dict:
    points = []
    for idx in range(count):
        points.append(
            {
                "kind": "flight",
                "category": "commercial",
                "label": f"FLT{idx:03d}",
                "lat": 10.0 + (idx % 3),
                "lon": -20.0 - (idx % 5),
                "altitude_ft": 30000,
                "speed_kts": 450,
                "heading_deg": 90,
                "speed_heat": 0.6,
                "vol_heat": 0.2,
            }
        )
    return {"points": points, "warnings": []}


def test_tracker_stack_fits_console_height():
    feed = MarketFeed()
    snapshot = _build_snapshot(120)
    console = Console(width=120, height=28, force_terminal=True)
    compact_height = console.height < 32
    sidebar = build_sidebar(
        [("Trackers", {"1": "Flights", "2": "Shipping", "3": "Combined"})],
        show_main=True,
        show_back=True,
        show_exit=True,
        compact=True,
    ) if not compact_height else None
    status_panel = build_status_header(
        "Tracker Status",
        [
            ("Mode", "combined"),
            ("Auto Refresh", "Off"),
            ("Commercial", "Off"),
            ("Private", "Off"),
        ],
        compact=True,
    ) if not compact_height else None
    footer_panel = (
        Text("N/P page | 0 back | M main | X exit", style="dim")
        if compact_height
        else Panel(Text("N/P page | 0 back | M main | X exit", style="dim"))
    )

    def _layout(rows: int):
        return feed._build_tracker_stack(
            snapshot=snapshot,
            mode="combined",
            category_filter="all",
            max_rows=rows,
            row_offset=0,
            sidebar=sidebar,
            status_panel=status_panel,
            footer_panel=footer_panel,
            include_commercial=False,
            include_private=False,
        )

    rows = fit_renderable_to_height(console, _layout, max_items=len(snapshot["points"]), min_items=1)
    lines = console.render_lines(_layout(rows), console.options)
    assert len(lines) <= console.height
