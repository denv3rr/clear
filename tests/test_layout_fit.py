from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from utils.layout import fit_renderable_to_height


def _build_panel(row_count: int) -> Panel:
    table = Table()
    table.add_column("A")
    for idx in range(row_count):
        table.add_row(str(idx))
    return Panel(table)


def test_fit_renderable_to_height_respects_console_height():
    console = Console(width=60, height=10, force_terminal=True)
    rows = fit_renderable_to_height(console, _build_panel, max_items=20, min_items=1)
    assert rows >= 1
    lines = console.render_lines(_build_panel(rows), console.options)
    assert len(lines) <= console.height
