import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
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
            ("1", "👥 Client Manager", "View portfolios, add clients, manage accounts"),
            ("2", "📈 Market Data", "Live Tickers, Futures, Commodities (Finnhub/Yahoo)"),
            ("3", "🧮 Financial Toolkit", "Monte Carlo, Valuations, P&L Calculator"),
            ("4", "⚙️ Settings", "API Config, User Preferences"),
            ("0", "🚪 Exit", "Securely close the session")
        ]

        # Build Rich Table
        table = Table(box=None, padding=(0, 2), collapse_padding=True, show_header=False)
        table.add_column("Key", style="bold gold1", width=4, justify="right")
        table.add_column("Module", style="bold white", width=25)
        table.add_column("Description", style="italic grey70")

        for key, name, desc in menu_options:
            table.add_row(f"[{key}]", name, desc)

        # Wrap in a Panel
        panel = Panel(
            Align.center(table),
            subtitle="[dim]Select a module number[/dim]",
            box=box.ROUNDED,
            padding=(1, 2),
            border_style="blue"
        )
        return panel

    def display(self) -> str:
        """
        Renders the menu and returns the user's selected action key.
        """
        
        main_panel = self._build_main_menu_frame()
        self.console.print(main_panel)
        
        # Map input keys to logical action codes
        action_map = {
            "1": "client_mgr",
            "2": "market_data",
            "3": "financial_toolkit",
            "4": "settings",
            "0": "exit"
        }
        
        choice = InputSafe.get_option(list(action_map.keys()), prompt_text="[>]")
        action = action_map[choice]

        if action == "exit":
            # Apply Burn animation to the main menu frame before exiting
            self.text_fx.play_burn(main_panel)
            self.console.clear()
        elif action == "settings":
            # Run the settings module
            self.settings_module.run()
            
        return action