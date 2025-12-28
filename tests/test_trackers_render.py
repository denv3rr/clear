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
