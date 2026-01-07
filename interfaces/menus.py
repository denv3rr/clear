import sys
import os
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich import box
from rich.console import Group

from utils.input import InputSafe
from interfaces.settings import SettingsModule
from interfaces.shell import ShellRenderer
from utils.system import SystemHost
from utils.world_clocks import build_world_clocks_panel
from interfaces.menu_layout import build_sidebar, compact_for_width
from modules.client_mgr.data_handler import DataHandler

class MainMenu:
    """
    The Primary Dashboard Navigation.
    """
    def __init__(self):
        self.console = Console()
        self.settings_module = SettingsModule()
        self._first_render = True

    @staticmethod
    def _bulletin_art() -> str:
        return r"""
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⠦⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠄⣼⢣⡷⢶⣭⣛⠲⢤⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡞⣼⢣⡟⣰⠶⣤⣍⡛⠷⢮⣝⡓⠦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣠⢠⢏⡾⣡⡟⣼⠏⣴⣦⣍⣙⠻⠶⣬⣝⡛⠶⣭⣛⡲⢤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣴⢣⢏⡾⣱⠏⣼⢃⣾⢃⣤⣍⣙⠛⠷⣦⣭⣙⡛⠶⣭⣙⡳⠮⣥⡀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⡴⣱⢣⢏⡾⣱⢏⣼⢃⡾⢃⣾⢋⣉⠛⠻⠷⣦⣬⣉⡛⠳⢶⣭⣙⡓⠶⣥⡀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⡠⡼⣱⣣⢏⡞⣱⢏⡾⢡⡿⢡⡿⢁⣾⠛⠻⠿⣶⣦⣬⣉⡛⠻⠶⣦⣭⣙⡛⠶⣤⡀⠀⠀⠀⠀⠀⠀
⠀⠀⡽⣱⣣⢏⡞⣼⢃⡾⣡⡟⣰⡟⢡⡿⢃⣼⣷⣶⣤⣤⣉⡙⠛⠿⠶⣦⣬⣉⣛⠻⠶⣤⡀⠀⠀⠀⠀⠀
⠀⠀⡽⣱⢫⡞⣼⢣⡟⣱⠟⣰⡟⣰⡿⢁⣾⠏⣠⣄⣉⡉⠛⠛⠿⠷⣶⣤⣬⣉⡛⠛⠷⢶⣤⡀⠀⠀⠀⠀
⠀⠀⢱⢣⠟⡼⢡⡟⣴⠏⣼⠏⣴⠟⣠⡿⠃⣴⡿⠛⠛⠿⠿⢷⣶⣦⣤⣌⣉⡙⠛⠻⠷⢶⣦⣥⡀⠀⠀⠀
⠀⠀⢠⢟⡾⣱⠟⣼⢋⣾⢋⣼⠏⣰⡿⢁⣾⠟⢀⣶⣶⣶⣤⣤⣄⣈⣉⠉⠛⠛⠿⠿⢶⣶⣤⣬⣁⡀⠀⠀
⠀⠀⢈⡾⣱⢏⣼⢃⡾⢃⣾⢃⣼⠟⣠⣿⡋⠀⠈⠉⠉⠙⠛⠛⠻⠿⠿⢿⣿⣷⣶⣶⣦⣤⣌⣉⣉⡓⠀⠀
⠀⠀⠈⣴⢋⡾⢡⡿⢡⡿⢁⣾⠋⠰⠿⠿⠿⣿⣿⣿⣶⣶⣶⣦⣤⣤⣤⣀⣀⣀⡉⠉⠉⠙⠛⠛⠿⠟⠃⠀
⠀⠀⠀⢣⡾⣱⡟⣰⡟⢡⣿⣷⣶⣶⣤⣤⣤⣤⣤⣀⣀⣉⣉⣉⡉⠙⠛⠛⠛⠛⠿⠿⠿⠛⠁⠀⠀⠀⠀⠀
⠀⠀⠀⡟⣰⠏⣴⣿⣤⣤⣤⣤⣤⣌⣉⣉⣉⣉⣉⣉⣛⡛⠛⠛⠛⠛⠻⠿⠛⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠼⠯⢤⣤⣤⣭⣭⢭⣭⣭⣍⣉⣉⣉⣉⣉⣙⣋⣛⡛⠛⠛⠉
"""
    def _build_stats_grid(self, items, two_column: bool):
        """
        Builds a responsive stats grid.
        - two_column=True → label/value | label/value
        - two_column=False → label/value stacked
        """
        if two_column:
            grid = Table.grid(expand=True, padding=(0, 2))
            grid.add_column(style="bold cyan", width=14)
            grid.add_column(style="white")
            grid.add_column(style="bold cyan", width=14)
            grid.add_column(style="white")

            half = (len(items) + 1) // 2
            left = items[:half]
            right = items[half:]

            max_rows = max(len(left), len(right))
            for i in range(max_rows):
                l = left[i] if i < len(left) else ("", "")
                r = right[i] if i < len(right) else ("", "")
                grid.add_row(l[0], l[1], r[0], r[1])
        else:
            grid = Table.grid(expand=True, padding=(0, 1))
            grid.add_column(style="bold cyan", width=14)
            grid.add_column(style="white")

            for label, value in items:
                grid.add_row(label, value)

        return grid

    def _build_two_column_stats(self, left_items, right_items):
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(style="bold cyan", width=14)
        grid.add_column(style="white")
        grid.add_column(style="bold cyan", width=14)
        grid.add_column(style="white")

        max_rows = max(len(left_items), len(right_items))
        for i in range(max_rows):
            l = left_items[i] if i < len(left_items) else ("", "")
            r = right_items[i] if i < len(right_items) else ("", "")
            grid.add_row(l[0], l[1], r[0], r[1])

        return grid

    def _build_bulletin_panel(self, panel_width: int, client_count: int = 0) -> Panel:
        """Main menu bulletin board with status and hints."""
        data = {}
        try:
            data = SystemHost.get_info() or {}
        except Exception:
            data = {}

        user = data.get("user", "User")
        host = data.get("hostname", "Host")
        os_name = data.get("os", "Unknown OS")
        cpu = data.get("cpu_usage", "N/A")
        mem = data.get("mem_usage", "N/A")

        finnhub_ok = "YES" if os.getenv("FINNHUB_API_KEY") else "NO"
        flight_ok = "YES" if (os.getenv("FLIGHT_DATA_URL") or os.getenv("FLIGHT_DATA_PATH")) else "NO"
        shipping_ok = "YES" if os.getenv("SHIPPING_DATA_URL") else "NO"

        title = Text()
        title.append("\nWelcome back, ", style="bold white")
        title.append(user, style="bold cyan")
        title.append(".", style="bold white")

        cwd = os.getcwd()
        data_file = os.path.join(cwd, "data", "clients.json")
        settings_file = os.path.join(cwd, "config", "settings.json")

        stats_items = [
            ("Host", str(host)),
            ("OS", str(os_name)),
            ("CPU", str(cpu)),
            ("Memory", str(mem)),
            ("Workdir", cwd),
            ("Python", data.get("python_version", "N/A")),
            ("CPU Cores", str(data.get("cpu_cores", "N/A"))),
            ("Finnhub", finnhub_ok),
            ("Flight Feed", flight_ok),
            ("Shipping", shipping_ok),
            ("Data File", "FOUND" if os.path.exists(data_file) else "MISSING"),
            ("Settings", "FOUND" if os.path.exists(settings_file) else "MISSING"),
        ]

        two_column = panel_width >= 110
        stats = self._build_stats_grid(stats_items, two_column)

        hint_rows = [
            "Press 2 for Markets, then 5 for Global Trackers.",
            "Use G in Trackers for the GUI map.",
            "Macro Dashboard loads on demand from Markets.",
        ]
        hints = Text()
        show_tips = bool(self.settings_module.settings.get("display", {}).get("show_tips", False))
        if show_tips:
            for idx, line in enumerate(hint_rows):
                suffix = "\n" if idx < len(hint_rows) - 1 else ""
                if line:
                    hints.append(f"• {line}{suffix}", style="bold gold1")
                else:
                    hints.append(f"{suffix}")

        ascii_art = self._bulletin_art()
        inner_width = max(40, panel_width - 8)
        inner_width -= inner_width % 2
        left_width = inner_width // 2
        right_width = inner_width // 2
        if ascii_art:
            trimmed = ascii_art.strip("\n")
            centered_lines = []
            for line in trimmed.splitlines():
                if not line:
                    centered_lines.append("")
                    continue
                line = line[:right_width]
                line_len = len(line)
                pad = max(0, (right_width - line_len) // 2)
                centered_lines.append((" " * pad) + line)
            ascii_art = "\n".join(centered_lines)

        left = Table.grid(expand=True)
        left.add_column(width=left_width, overflow="crop", no_wrap=True)
        left.add_row(Align.center(title))
        left.add_row(Text(""))
        left.add_row(Align.center(stats))
        left.add_row(Text(""))
        if show_tips:
            left.add_row(Align.center(hints))

        right = Table.grid(expand=True)
        right.add_column(width=right_width, overflow="crop", no_wrap=True)
        if ascii_art:
            right.add_row(Align.left(Text(ascii_art, overflow="crop", no_wrap=True)))
        else:
            right.add_row(Align.center(Text("SEPERET.COM", style="dim")))   

        vertical_layout = panel_width < 120 or right_width < 50
        if not vertical_layout:
            clock_panel = build_world_clocks_panel(left_width)
            if clock_panel:
                left.add_row(Align.center(clock_panel))
        layout = Table.grid(expand=True)
        if vertical_layout:
            layout.add_column(ratio=1)
            if ascii_art:
                layout.add_row(Align.center(Text(ascii_art, overflow="crop", no_wrap=True)))
            layout.add_row(Align.center(left))
        else:
            layout.add_column(width=left_width, overflow="crop", no_wrap=True)   
            layout.add_column(width=right_width, overflow="crop", no_wrap=True)  
            layout.add_row(left, right)

        panel = Panel(
            Align.center(layout),
            box=box.ROUNDED,
            padding=(1, 3),
            border_style="blue",
            width=panel_width,
        )
        return panel

    @staticmethod
    @staticmethod
    def _estimate_bulletin_rows(stat_rows: int, hint_rows: int) -> int:
        # title + spacer + blank line + stats + hints + padding top/bottom
        base_rows = 2 + 1 + stat_rows + hint_rows
        return base_rows + 2

    @staticmethod
    def clear_console():
        # Windows
        if os.name == 'nt':
            _ = os.system('cls')
        # macOS and Linux
        else:
            _ = os.system('clear')

    def display(self) -> str:
        """
        Renders the menu and returns the user's selected action key.
        """
        
        action_map = {
            "1": "client_mgr",
            "2": "market_data",
            "3": "settings",
            "4": "intel_reports",
            "5": "global_trackers",
            "6": "assistant",
            "0": "exit",
            "x": "exit"
        }
        compact = compact_for_width(self.console.width)
        sidebar_width = 22 if compact else 26
        available_width = max(80, self.console.width - (sidebar_width * 2) - 4)
        panel_width = min(200, available_width)
        client_count = len(DataHandler.load_clients() or [])
        main_panel = self._build_bulletin_panel(panel_width, client_count=client_count)
        min_rows = self._estimate_bulletin_rows(stat_rows=7, hint_rows=3)
        sidebar = build_sidebar(
            [
                ("Modules", {
                    "1": "Client Manager",
                    "2": "Markets",
                    "3": "Settings",
                    "4": "Reports",
                    "5": "Global Trackers",
                    "6": "Assistant",
                }),
                ("Session", {"0": "Exit"}),
            ],
            show_main=False,
            show_back=False,
            show_exit=False,
            compact=compact,
            min_rows=min_rows,
        )
        choice = ShellRenderer.render_and_prompt(
            Group(Align.center(main_panel)),
            context_actions={
                "1": "Client Manager",
                "2": "Markets",
                "3": "Settings",
                "4": "Reports",
                "5": "Global Trackers",
                "0": "Exit",
            },
            valid_choices=list(action_map.keys()),
            prompt_label=">",
            show_main=False,
            show_back=False,
            show_exit=True,
            # keep the welcome splash visible under the first menu render
            preserve_previous=self._first_render,
            show_header=False,
            sidebar_override=sidebar,
            balance_sidebar=True,
        )
        self._first_render = False
        
        action = action_map[choice]

        if action == "exit":
            self.clear_console()

        return action
