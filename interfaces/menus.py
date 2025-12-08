import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box

from utils.input import InputSafe

class MainMenu:
    """
    The Primary Dashboard Navigation.
    """
    def __init__(self):
        self.console = Console()

    def display(self) -> str:
        """
        Renders the menu and returns the user's selected action key.
        """
        self.console.clear()
        
        # 1. Define the Menu Options
        # Format: (Key, Label, Description)
        menu_options = [
            ("1", "👥 Client Manager", "View portfolios, add clients, manage accounts"),
            ("2", "📈 Market Data", "Live Tickers, Futures, Commodities (Finnhub/Yahoo)"),
            ("3", "🧮 Financial Toolkit", "Monte Carlo, Valuations, P&L Calculator"),
            ("4", "⚙️  Settings", "API Config, User Preferences"),
            ("0", "🚪 Exit", "Securely close the session")
        ]

        # 2. Build the Rich Table
        table = Table(box=None, padding=(0, 2), collapse_padding=True, show_header=False)
        table.add_column("Key", style="bold gold1", width=4, justify="right")
        table.add_column("Module", style="bold white", width=25)
        table.add_column("Description", style="italic grey70")

        for key, name, desc in menu_options:
            table.add_row(f"[{key}]", name, desc)

        # 3. Wrap in a Panel
        panel = Panel(
            Align.center(table),
            title="[bold blue]CLEAR SUITE DASHBOARD[/bold blue]",
            subtitle="[dim]Select a module number[/dim]",
            box=box.ROUNDED,
            padding=(1, 2),
            border_style="blue"
        )

        # 4. Print and Ask
        self.console.print(panel)
        
        # Map input keys to logical action codes
        action_map = {
            "1": "client_mgr",
            "2": "market_data",
            "3": "fin_tools",
            "4": "settings",
            "0": "exit"
        }
        
        # Get Valid Input
        choice = InputSafe.get_option(valid_choices=list(action_map.keys()), prompt_text="ACCESS MODULE >")
        
        return action_map.get(choice, "none")