import sys
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich import box

from utils.input import InputSafe
from utils.text_fx import TextEffectManager
from interfaces.settings import SettingsModule

class MainMenu:
    """
    The Primary Dashboard Navigation.
    """
    def __init__(self):
        self.console = Console()
        self.text_fx = TextEffectManager()
        self.settings_module = SettingsModule()

    def _build_main_menu_frame(self) -> Panel:
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
            width=200
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
        
        main_panel = self._build_main_menu_frame()
        self.console.print(Align.center(main_panel))
        
        action_map = {
            "1": "client_mgr",
            "2": "market_data",
            "3": "settings",
            "0": "exit"
        }

        panel_width = 200
        inner_content_offset = 28
        terminal_width = self.console.width
        
        # 1. Calculate the base left padding needed to center the 200-width panel
        base_left_padding = max(0, (terminal_width - panel_width) // 2)
        
        # 2. Add the inner content offset (6) to align the prompt with the menu text
        total_left_padding = base_left_padding + inner_content_offset
        
        # Prepend the spaces to the prompt text
        padded_prompt = Text(" " * total_left_padding + "[>]")
        
        choice = InputSafe.get_option(list(action_map.keys()), prompt_text=padded_prompt)
        
        action = action_map[choice]

        if action == "exit":
            # To apply Burn animation to the main menu frame before exiting
            # (or just import/change as needed)
            # UNCOMMENT:
            # self.text_fx.play_burn(main_panel)

            #clear the console after animation
            self.clear_console()

        return action