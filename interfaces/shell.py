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
    _live_prompt_enabled = False

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
    ) -> str:
        console = Console()
        width = console.width
        choices = [str(c).lower() for c in valid_choices]

        try:
            import msvcrt
            use_live = bool(live_input) and ShellRenderer._live_prompt_enabled
        except Exception:
            use_live = False

        input_text = ""
        error_text = ""
        normalized_label = str(prompt_label).strip("[]").strip() or ">"
        prompt_width = 0
        has_error = False
        prompt_prefix = "› Input: "
        prompt_prefix_len = len(prompt_prefix)

        def _truncate_line(line: str, width: int) -> str:
            if width <= 0:
                return ""
            if len(line) <= width:
                return line.ljust(width)
            if width <= 3:
                return line[:width]
            return line[:width - 3] + "..."

        def build_layout(include_prompt: bool = True) -> Table:
            nonlocal prompt_width, has_error
            resolved_show_sidebar = show_sidebar
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
            busy = time.time() < ShellRenderer._busy_until
            blink_on = int(time.time() * 2) % 2 == 0
            if busy:
                label = "•" if blink_on else " "
            else:
                label = "›"
            help_line = f"{label} Input: {input_text}"
            prompt_width = sidebar_width if sidebar_width > 0 else max(10, width - 2)
            has_error = bool(error_text)
            help_line = _truncate_line(help_line, prompt_width)
            help_text = build_scrolling_line(
                help_line,
                preset="prompt",
                width=prompt_width,
                highlights=[str(c).upper() for c in valid_choices],
            )
            if error_text:
                prompt_block = Group(help_text, Text(error_text, style="red"))
            else:
                prompt_block = help_text

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
                    if include_prompt:
                        body.add_row(prompt_block, Text(""), Text(""))
                else:
                    body.add_column(width=sidebar_width)
                    body.add_column(ratio=1)
                    body.add_row(sidebar, content)
                    if include_prompt:
                        body.add_row(prompt_block, Text(""))
            else:
                body.add_column(ratio=1)
                body.add_row(content)
                if include_prompt:
                    body.add_row(prompt_block)
            layout.add_row(body)
            return layout

        if not use_live:
            try:
                import msvcrt
                use_tty_prompt = True
            except Exception:
                use_tty_prompt = False

            def _render_layout() -> None:
                layout = build_layout(include_prompt=False)
                if not (preserve_previous and ShellRenderer._first_render):
                    console.clear()
                    print("\x1b[3J", end="")
                ShellRenderer._first_render = False
                console.print(layout)
                lines_up = 1 if has_error else 0
                try:
                    if lines_up:
                        console.file.write(f"\x1b[{lines_up}A\r")
                    else:
                        console.file.write("\r")
                    max_input_len = max(0, prompt_width - prompt_prefix_len)
                    visible_len = min(len(input_text), max_input_len)
                    console.file.write(f"\x1b[{prompt_prefix_len + visible_len}C")
                    console.file.flush()
                except Exception:
                    pass

            def _render_prompt_line() -> None:
                label = "•" if (time.time() < ShellRenderer._busy_until and int(time.time() * 2) % 2 == 0) else "›"
                line_text = f"{label} Input: {input_text}"
                line_text = _truncate_line(line_text, prompt_width)
                prompt_text = build_scrolling_line(
                    line_text,
                    preset="prompt",
                    width=prompt_width,
                    highlights=[str(c).upper() for c in valid_choices],
                )
                try:
                    console.file.write("\r\x1b[2K")
                    console.print(prompt_text, end="")
                    max_input_len = max(0, prompt_width - prompt_prefix_len)
                    visible_len = min(len(input_text), max_input_len)
                    console.file.write("\r")
                    console.file.write(f"\x1b[{prompt_prefix_len + visible_len}C")
                    console.file.flush()
                except Exception:
                    pass

            _render_layout()
            if not use_tty_prompt:
                selection = console.input("")
                return selection.lower()

            last_input = None
            last_tick = None
            last_busy = None
            last_blink = None
            while True:
                now = time.time()
                busy = now < ShellRenderer._busy_until
                blink_on = int(now * 2) % 2 == 0
                tick = int(now * 6)
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\r", "\n"):
                        val = input_text.strip().lower()
                        if val in choices:
                            return val
                        error_text = f"Invalid. Options: {', '.join(valid_choices)}"
                        input_text = ""
                        _render_layout()
                        last_input = None
                        last_tick = None
                        continue
                    if ch == "\b":
                        input_text = input_text[:-1]
                    elif ch == "\x03":
                        raise KeyboardInterrupt
                    elif ch.isprintable():
                        input_text += ch
                    if error_text:
                        error_text = ""
                        _render_layout()
                        last_input = None
                        last_tick = None
                        continue
                needs_update = False
                if input_text != last_input:
                    needs_update = True
                if busy and blink_on != last_blink:
                    needs_update = True
                if tick != last_tick:
                    needs_update = True
                if busy != last_busy:
                    needs_update = True
                if needs_update:
                    _render_prompt_line()
                    last_input = input_text
                    last_tick = tick
                    last_blink = blink_on
                    last_busy = busy
                time.sleep(0.05)

        if not (preserve_previous and ShellRenderer._first_render):
            console.clear()
            print("\x1b[3J", end="")
        ShellRenderer._first_render = False

        last_input = None
        last_error = None
        last_blink = None
        last_busy = None
        last_tick = None
        last_render = None

        with Live(
            build_layout(),
            console=console,
            refresh_per_second=4,
            screen=False,
            auto_refresh=False,
        ) as live:
            while True:
                now = time.time()
                busy = now < ShellRenderer._busy_until
                blink_on = int(now * 2) % 2 == 0
                tick = int(now * 6)
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
                needs_update = False
                if input_text != last_input or error_text != last_error:
                    needs_update = True
                if busy and blink_on != last_blink:
                    needs_update = True
                if (input_text or error_text) and tick != last_tick:
                    needs_update = True
                if busy != last_busy:
                    needs_update = True
                if needs_update or last_render is None:
                    layout = build_layout()
                    live.update(layout, refresh=True)
                    last_render = layout
                    last_input = input_text
                    last_error = error_text
                    last_blink = blink_on
                    last_busy = busy
                    last_tick = tick
                time.sleep(0.05)
