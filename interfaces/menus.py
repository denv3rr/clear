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

class MainMenu:
    """
    The Primary Dashboard Navigation.
    """
    def __init__(self):
        self.console = Console()
        self.text_fx = TextEffectManager()
        self.settings_module = SettingsModule()

    def _build_main_menu_frame(self, panel_width: int) -> Panel:
        """Helper to build the main menu Rich panel."""
        menu_options = [
            ("1", "Client Manager", "View portfolios, add clients, manage accounts"),
            ("2", "Markets", "Tickers, Futures, Commodities ([green]LIVE[/green])"),
            ("3", "Settings", "API Config, User Preferences"),
            ("0", "Exit", "Securely close the session")
        ]

        # Build Rich Table
        table = Table(box=None, padding=(0, 2), collapse_padding=True, show_header=False)
        table.add_column("Key", style="bold gold1", width=4, justify="right")
        table.add_column("Module", style="bold white")
        table.add_column("Description", style="italic grey70")

        for key, name, desc in menu_options:
            table.add_row(key, name, desc)

        # Wrap in a Panel
        panel = Panel(
            Align.center(table),
            box=box.ROUNDED,
            padding=(1, 5),
            border_style="blue",
            width=panel_width
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
            "0": "exit",
            "x": "exit"
        }
        panel_width = min(140, max(72, self.console.width - 8))
        main_panel = self._build_main_menu_frame(panel_width)
        choice = ShellRenderer.render_and_prompt(
            Group(Align.center(main_panel)),
            context_actions={
                "1": "Client Manager",
                "2": "Markets",
                "3": "Settings",
                "0": "Exit"
            },
            valid_choices=list(action_map.keys()),
            prompt_label="[>]",
            show_main=False,
            show_back=False,
            show_exit=True,
            preserve_previous=True,
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
