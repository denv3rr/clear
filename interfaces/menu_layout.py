from typing import Dict, List, Tuple

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


def build_sidebar(
    sections: List[Tuple[str, Dict[str, str]]],
    show_main: bool = True,
    show_back: bool = True,
    show_exit: bool = True,
    compact: bool = False,
    min_rows: int = 0,
) -> Panel:
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Key", style="bold cyan", width=3, justify="left")
    table.add_column("Action", style="white", overflow="crop", no_wrap=True)

    for title, actions in sections:
        if title and not compact:
            table.add_row("", Text(title.upper(), style="dim", overflow="crop", no_wrap=True))
        for key, label in actions.items():
            table.add_row(str(key), label)
        if not compact:
            table.add_row("", "")

    core = {}
    if show_back:
        core["0"] = "Back"
    if show_main:
        core["M"] = "Main Menu"
    if show_exit:
        core["X"] = "Exit"
    if core:
        if not compact:
            table.add_row("", Text("SESSION", style="dim", overflow="crop", no_wrap=True))
        for key, label in core.items():
            table.add_row(str(key), label)

    while min_rows > 0 and table.row_count < min_rows:
        table.add_row("", "")

    width = 22 if compact else 26
    return Panel(table, title="[bold]Actions[/bold]", box=box.ROUNDED, width=width)


def compact_for_width(width: int) -> bool:
    return width < 110


def build_status_header(title: str, items: List[Tuple[str, str]], compact: bool = False) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold cyan", width=14 if not compact else 10)
    table.add_column(style="white")
    for key, value in items:
        table.add_row(str(key), str(value))
    return Panel(table, title=title, box=box.SQUARE, border_style="dim")
