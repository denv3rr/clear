from rich.console import Console

from modules.market_data.trackers import GlobalTrackers


def test_tracker_render_outputs_placeholder_when_empty():
    trackers = GlobalTrackers()
    snapshot = {"mode": "combined", "count": 0, "warnings": [], "points": []}
    panel = trackers.render(snapshot=snapshot)
    console = Console(record=True, width=120)
    console.print(panel)
    output = console.export_text()
    assert "No live" in output


def test_tracker_render_compact_hides_heat_columns():
    trackers = GlobalTrackers()
    snapshot = {
        "mode": "combined",
        "count": 1,
        "warnings": [],
        "points": [{"kind": "flight", "category": "cargo", "label": "TEST123", "lat": 10.0, "lon": 20.0}],
    }
    panel = trackers.render(snapshot=snapshot, compact=True)
    console = Console(record=True, width=80)
    console.print(panel)
    output = console.export_text()
    assert "Spd Heat" not in output
    assert "Vol Heat" not in output
