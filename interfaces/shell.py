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
    _busy_until = 0.0
    _live_prompt_enabled = True

    @staticmethod
    def enable_live_prompt(enabled: bool = True) -> None:
        ShellRenderer._live_prompt_enabled = bool(enabled)

    @staticmethod
    def set_busy(seconds: float = 1.0) -> None:
        try:
            duration = float(seconds)
        except Exception:
            duration = 0.0
        if duration > 0:
            ShellRenderer._busy_until = max(ShellRenderer._busy_until, time.time() + duration)

    @staticmethod
    def _build_sidebar(
        context_actions: Dict[str, str],
        show_main: bool = True,
        show_back: bool = True,
        show_exit: bool = True,
    ) -> Panel:
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Key", style="bold cyan", width=3, justify="left")
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

        return Panel(table, title="[bold]Actions[/bold]", box=box.ROUNDED, width=26)

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
        balance_sidebar: bool = True,
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

        sidebar_width = getattr(sidebar, "width", None) or 30
        body = Table.grid(expand=True)
        if balance_sidebar:
            body.add_column(width=sidebar_width)
            body.add_column(ratio=1)
            body.add_column(width=sidebar_width)
            body.add_row(sidebar, content, Text(""))
        else:
            body.add_column(width=sidebar_width)
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
        balance_sidebar: bool = True,
        show_sidebar: bool = True,
        auto_disable_live_on_overflow: bool = True,
    ) -> str:
        console = Console()
        width = console.width
        choices = [str(c).lower() for c in valid_choices]
        options_map = context_actions or {}
        ordered_choices = list(options_map.keys()) if options_map else list(choices)
        for extra in ("0", "m", "x"):
            if extra in choices and extra not in ordered_choices:
                ordered_choices.append(extra)
        selection_idx = 0

        try:
            import msvcrt
            has_tty = True
        except Exception:
            has_tty = False

        def _build_selector_panel() -> Optional[Panel]:
            if not options_map or not ordered_choices:
                return None
            table = Table.grid(padding=(0, 1))
            table.add_column(justify="left", ratio=1)
            for idx, key in enumerate(ordered_choices):
                label = options_map.get(key, "")
                highlight = idx == selection_idx
                prefix = " " if highlight else "  "
                style = "bold cyan" if highlight else "dim"
                line = f"{prefix}[{str(key).upper()}] {label}"
                table.add_row(Text(line, style=style, overflow="crop"))
            return Panel(table, box=box.ROUNDED, border_style="cyan", padding=(0, 1), title="Select")

        def _build_prompt_block() -> Group:
            selector_panel = _build_selector_panel()
            label = "•" if (time.time() < ShellRenderer._busy_until and int(time.time() * 2) % 2 == 0) else "›"
            raw = f"{label} {input_text}"
            # Only scroll the prompt text, not the entire panel width.
            width_local = max(10, len(raw) + 4)
            prompt_render = build_scrolling_line(
                raw,
                preset="prompt",
                width=width_local,
                highlights=[str(c).upper() for c in valid_choices],
            )
            if selector_panel:
                return Group(prompt_render, selector_panel)
            return Group(prompt_render)

        def _build_layout(include_prompt: bool = False) -> Table:
            resolved_show_sidebar = show_sidebar and not options_map
            if resolved_show_sidebar and not context_actions and not show_main and not show_back and not show_exit and sidebar_override is None:
                resolved_show_sidebar = False
            sidebar = None
            sidebar_width = 0
            if resolved_show_sidebar:
                sidebar = sidebar_override or ShellRenderer._build_sidebar(
                    context_actions or {},
                    show_main=show_main,
                    show_back=show_back,
                    show_exit=show_exit,
                )
                sidebar_width = getattr(sidebar, "width", None) or 30

            layout = Table.grid(expand=True)
            layout.add_column(ratio=1)
            if show_header:
                header = ShellRenderer._ticker.render(width)
                layout.add_row(header)

            body = Table.grid(expand=True)
            if sidebar:
                if balance_sidebar:
                    body.add_column(width=sidebar_width)
                    body.add_column(ratio=1)
                    body.add_column(width=sidebar_width)
                    body.add_row(sidebar, content, Text(""))
                else:
                    body.add_column(width=sidebar_width)
                    body.add_column(ratio=1)
                    body.add_row(sidebar, content)
            else:
                body.add_column(ratio=1)
                body.add_row(content)

            layout.add_row(body)
            if include_prompt:
                layout.add_row(_build_prompt_block())
            return layout

        # Always render the static page once; prompt updates separately.
        if not (preserve_previous and ShellRenderer._first_render):
            console.clear()
            print("\x1b[3J", end="")
        ShellRenderer._first_render = False
        console.print(_build_layout(include_prompt=False))

        # Simple fallback when no tty/live capability.
        if not has_tty or not ShellRenderer._live_prompt_enabled or not live_input:
            console.print(_build_prompt_block())
            selection = console.input(f"{prompt_label} ").strip().lower()
            if not selection and ordered_choices:
                return str(ordered_choices[selection_idx]).lower()
            return selection

        input_text = ""
        error_text = ""
        last_input = None
        last_error = None
        last_blink = None
        last_busy = None
        last_selection = None

        with Live(_build_prompt_block(), console=console, refresh_per_second=8, screen=False, auto_refresh=False) as live:
            while True:
                now = time.time()
                busy = now < ShellRenderer._busy_until
                blink_on = int(now * 2) % 2 == 0
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x00", "\xe0"):
                        try:
                            arrow = msvcrt.getwch()
                        except Exception:
                            arrow = ""
                        if ordered_choices:
                            if arrow in ("H", "K"):  # up/left
                                selection_idx = (selection_idx - 1) % len(ordered_choices)
                            if arrow in ("P", "M"):  # down/right
                                selection_idx = (selection_idx + 1) % len(ordered_choices)
                        continue
                    if ch in ("\r", "\n"):
                        val = input_text.strip().lower()
                        if not val and ordered_choices:
                            return str(ordered_choices[selection_idx]).lower()
                        if val in choices:
                            return val
                        error_text = f"Invalid. Options: {', '.join(valid_choices)}"
                        input_text = ""
                        continue
                    if ch == "\b":
                        input_text = input_text[:-1]
                    elif ch == "\x03":
                        raise KeyboardInterrupt
                    elif ch.isprintable():
                        input_text += ch
                    if error_text:
                        error_text = ""
                        continue
                needs_update = False
                if input_text != last_input or error_text != last_error:
                    needs_update = True
                if busy != last_busy or blink_on != last_blink:
                    needs_update = True
                if selection_idx != last_selection:
                    needs_update = True
                if needs_update:
                    live.update(_build_prompt_block(), refresh=True)
                    last_input = input_text
                    last_error = error_text
                    last_blink = blink_on
                    last_busy = busy
                    last_selection = selection_idx
                time.sleep(0.08)

        return ""
