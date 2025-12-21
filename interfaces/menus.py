import sys
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich import box
from rich.console import Group

from utils.input import InputSafe
from utils.text_fx import TextEffectManager
from interfaces.settings import SettingsModule
from interfaces.shell import ShellRenderer
from utils.system import SystemHost
from interfaces.menu_layout import build_sidebar, compact_for_width

class MainMenu:
    """
    The Primary Dashboard Navigation.
    """
    def __init__(self):
        self.console = Console()
        self.text_fx = TextEffectManager()
        self.settings_module = SettingsModule()

    def _build_bulletin_panel(self, panel_width: int) -> Panel:
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
        opensky_ok = "YES" if os.getenv("OPENSKY_USERNAME") and os.getenv("OPENSKY_PASSWORD") else "NO"
        shipping_ok = "YES" if os.getenv("SHIPPING_DATA_URL") else "NO"

        title = Text()
        title.append("Welcome back, ", style="bold white")
        title.append(user, style="bold cyan")
        title.append(".", style="bold white")

        stats = Table.grid(padding=(0, 1))
        stats.add_column(style="bold cyan", width=14)
        stats.add_column(style="white")
        stats.add_row("Host", str(host))
        stats.add_row("OS", str(os_name))
        stats.add_row("CPU", str(cpu))
        stats.add_row("Memory", str(mem))
        stats.add_row("Finnhub Key", finnhub_ok)
        stats.add_row("OpenSky Creds", opensky_ok)
        stats.add_row("Shipping URL", shipping_ok)

        hints = Table.grid(padding=(0, 1))
        hints.add_column(style="bold gold1", width=10)
        hints.add_column(style="dim")
        hints.add_row("Tip", "Press 2 for Markets, then 5 for Global Trackers.")
        hints.add_row("Tip", "Use G in Trackers for the GUI map.")
        hints.add_row("Tip", "Macro Dashboard loads on demand from Markets.")

        layout = Table.grid(expand=True)
        layout.add_column(ratio=1)
        layout.add_row(Align.center(title))
        layout.add_row(Align.center(stats))
        layout.add_row(Align.center(hints))

        panel = Panel(
            Align.center(layout),
            box=box.ROUNDED,
            padding=(1, 5),
            border_style="blue",
            width=panel_width,
            title="Bulletin",
        )
        return panel

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
            "0": "exit",
            "x": "exit"
        }
        panel_width = min(140, max(72, self.console.width - 8))
        main_panel = self._build_bulletin_panel(panel_width)
        compact = compact_for_width(self.console.width)
        sidebar = build_sidebar(
            [
                ("Modules", {
                    "1": "Client Manager",
                    "2": "Markets",
                    "3": "Settings",
                    "4": "Intel Reports",
                }),
                ("Session", {"0": "Exit"}),
            ],
            show_main=False,
            show_back=False,
            show_exit=False,
            compact=compact,
        )
        choice = ShellRenderer.render_and_prompt(
            Group(Align.center(main_panel)),
            context_actions={},
            valid_choices=list(action_map.keys()),
            prompt_label=">",
            show_main=False,
            show_back=False,
            show_exit=True,
            preserve_previous=True,
            show_header=False,
            sidebar_override=sidebar,
        )
        
        action = action_map[choice]

        if action == "exit":
            # To apply Burn animation to the main menu frame before exiting
            # (or just import/change as needed)
            # UNCOMMENT:
            # self.text_fx.play_burn(main_panel)

            #clear the console after animation
            self.clear_console()

        return action
