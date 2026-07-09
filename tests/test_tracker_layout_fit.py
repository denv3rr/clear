import sys
import types

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


def test_live_tracker_layout_initializes_compact_state(monkeypatch):
    feed = MarketFeed()
    feed.console = Console(width=100, height=28, force_terminal=True)
    snapshot = _build_snapshot(8)
    snapshot.update({"mode": "combined", "count": len(snapshot["points"])})
    monkeypatch.setattr(feed, "_tracker_snapshot", lambda mode, allow_refresh: snapshot)
    monkeypatch.setattr(feed.trackers, "refresh", lambda force=False: None)
    monkeypatch.setattr(feed.trackers, "get_snapshot", lambda mode="combined": snapshot)
    monkeypatch.setitem(
        sys.modules,
        "msvcrt",
        types.SimpleNamespace(kbhit=lambda: False, getwch=lambda: "0"),
    )

    class InitialLayoutRendered(Exception):
        pass

    class FakeLive:
        def __init__(self, renderable, *args, **kwargs):
            lines = feed.console.render_lines(renderable, feed.console.options)
            assert lines

        def __enter__(self):
            raise InitialLayoutRendered()

        def __exit__(self, exc_type, exc, tb):
            return False

    import rich.live

    monkeypatch.setattr(rich.live, "Live", FakeLive)

    try:
        feed.run_global_trackers()
    except InitialLayoutRendered:
        pass
