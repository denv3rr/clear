import time
from typing import Dict, List, Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.live import Live

from modules.market_data.yfinance_client import YahooWrapper
from utils.scroll_text import build_scrolling_line


class TickerStrip:
    def __init__(self, lanes: Optional[List[str]] = None, refresh_seconds: int = 30):
        self.console = Console()
        self.yahoo = YahooWrapper()
        self.lanes = lanes or ["Indices", "Big Tech", "FX", "Rates", "Crypto"]
        self.refresh_seconds = refresh_seconds
        self._last_refresh = 0
        self._snapshot = []
        self._offsets = {lane: 0 for lane in self.lanes}

    def _refresh(self) -> None:
        now = time.time()
        if (now - self._last_refresh) < self.refresh_seconds:
            return
        try:
            self._snapshot = self.yahoo.get_macro_snapshot(period="1d", interval="15m") or []
            self._last_refresh = now
        except Exception:
            self._snapshot = self._snapshot or []

    def _build_lane(self, lane: str, width: int) -> Text:
        items = [i for i in self._snapshot if i.get("category") == lane]
        if not items:
            return Text("data unavailable".ljust(width), style="dim")

        parts = []
        spans = []
        cursor = 0
        for item in items:
            ticker = item.get("ticker", "")
            price = float(item.get("price", 0.0) or 0.0)
            pct = float(item.get("pct", 0.0) or 0.0)
            arrow = "▲" if pct >= 0 else "▼"
            segment = f"{ticker} {price:,.2f} {arrow} {pct:+.2f}%"
            parts.append(segment)
            spans.append((cursor, cursor + len(segment), "green" if pct >= 0 else "red"))
            cursor += len(segment) + 5

        line = "  •  ".join(parts) + "  •  "
        if len(line) < width:
            line = line.ljust(width)

        offset = self._offsets.get(lane, 0) % max(1, len(line))
        doubled = line + line
        scrolled = doubled[offset:offset + width]
        self._offsets[lane] = offset + 1
        text = Text(scrolled)
        line_len = len(line)
        for start, end, style in spans:
            for shift in (0, line_len):
                s = start + shift
                e = end + shift
                if e <= offset or s >= offset + width:
                    continue
                clip_start = max(s, offset) - offset
                clip_end = min(e, offset + width) - offset
                if clip_end > clip_start:
                    text.stylize(style, int(clip_start), int(clip_end))
        return text

    def render(self, width: int) -> Panel:
        self._refresh()
        inner_width = max(10, width - 2)
        lines = []
        for lane in self.lanes:
            lines.append(self._build_lane(lane, inner_width))
        content = Group(*lines)
        return Panel(content, box=box.SQUARE, border_style="dim", padding=(0, 0))


class ShellRenderer:
    _ticker = TickerStrip()
    _first_render = True

    @staticmethod
    def _build_sidebar(
        context_actions: Dict[str, str],
        show_main: bool = True,
        show_back: bool = True,
        show_exit: bool = True,
    ) -> Panel:
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Key", style="bold cyan", width=5, justify="right")
        table.add_column("Action", style="white")

        if context_actions:
            for key, label in context_actions.items():
                table.add_row(str(key), label)
            table.add_row("", "")

        if show_back and "0" not in context_actions:
            table.add_row("0", "Back")
        if show_main:
            table.add_row("M", "Main Menu")
        if show_exit:
            table.add_row("X", "Exit")

        return Panel(table, title="[bold]Actions[/bold]", box=box.ROUNDED)

    @staticmethod
    def render(
        content: Group,
        context_actions: Optional[Dict[str, str]] = None,
        show_main: bool = True,
        show_back: bool = True,
        show_exit: bool = True,
        preserve_previous: bool = False,
        show_header: bool = True,
        sidebar_override: Optional[Panel] = None,
    ) -> None:
        console = Console()
        width = console.width
        sidebar = sidebar_override or ShellRenderer._build_sidebar(
            context_actions or {},
            show_main=show_main,
            show_back=show_back,
            show_exit=show_exit,
        )

        layout = Table.grid(expand=True)
        layout.add_column(ratio=1)
        if show_header:
            header = ShellRenderer._ticker.render(width)
            layout.add_row(header)

        body = Table.grid(expand=True)
        body.add_column(width=30)
        body.add_column(ratio=1)
        body.add_row(sidebar, content)

        layout.add_row(body)
        if not (preserve_previous and ShellRenderer._first_render):
            console.clear()
            print("\x1b[3J", end="")
        ShellRenderer._first_render = False
        console.print(layout)

    @staticmethod
    def render_and_prompt(
        content: Group,
        context_actions: Optional[Dict[str, str]],
        valid_choices: List[str],
        prompt_label: str = ">",
        show_main: bool = True,
        show_back: bool = True,
        show_exit: bool = True,
        preserve_previous: bool = False,
        show_header: bool = True,
        live_input: bool = True,
        sidebar_override: Optional[Panel] = None,
    ) -> str:
        console = Console()
        width = console.width
        choices = [str(c).lower() for c in valid_choices]

        try:
            import msvcrt
            use_live = live_input
        except Exception:
            use_live = False

        if not use_live:
            ShellRenderer.render(
                content,
                context_actions=context_actions,
                show_main=show_main,
                show_back=show_back,
                show_exit=show_exit,
                preserve_previous=preserve_previous,
                show_header=show_header,
            )
            from utils.input import InputSafe
            return InputSafe.get_option(valid_choices, prompt_text=prompt_label)

        input_text = ""
        error_text = ""
        normalized_label = str(prompt_label).strip("[]").strip() or ">"

        def build_layout() -> Table:
            sidebar = sidebar_override or ShellRenderer._build_sidebar(
                context_actions or {},
                show_main=show_main,
                show_back=show_back,
                show_exit=show_exit,
            )
            help_line = f"{normalized_label} {input_text}  Options: {', '.join([str(c).upper() for c in valid_choices])}"
            help_text = build_scrolling_line(
                help_line,
                preset="prompt",
                width=len(help_line),
                highlights=[str(c).upper() for c in valid_choices],
            )
            if error_text:
                error_line = Text(error_text, style="red")
                footer = Panel(Group(help_text, error_line), box=box.SQUARE, border_style="dim")
            else:
                footer = Panel(help_text, box=box.SQUARE, border_style="dim")

            layout = Table.grid(expand=True)
            layout.add_column(ratio=1)
            if show_header:
                header = ShellRenderer._ticker.render(width)
                layout.add_row(header)

            body = Table.grid(expand=True)
            body.add_column(width=30)
            body.add_column(ratio=1)
            body.add_row(sidebar, content)
            layout.add_row(body)
            layout.add_row(footer)
            return layout

        if not (preserve_previous and ShellRenderer._first_render):
            console.clear()
            print("\x1b[3J", end="")
        ShellRenderer._first_render = False

        with Live(build_layout(), console=console, refresh_per_second=12, screen=False) as live:
            while True:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\r", "\n"):
                        val = input_text.strip().lower()
                        if val in choices:
                            return val
                        error_text = f"Invalid. Options: {', '.join(valid_choices)}"
                        input_text = ""
                    elif ch == "\b":
                        input_text = input_text[:-1]
                    elif ch == "\x03":
                        raise KeyboardInterrupt
                    elif ch.isprintable():
                        input_text += ch
                live.update(build_layout(), refresh=True)
                time.sleep(0.1)
