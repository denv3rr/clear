import sys
from rich.console import Console

# Import internal modules
from interfaces.menus import MainMenu
from interfaces.shell import MainMenuRequested
from utils.input import InputSafe
from modules.market_data.feed import MarketFeed
from modules.client_mgr.manager import ClientManager
from interfaces.settings import SettingsModule

class ClearApp:
    """
    The Central Controller.
    Maintains the application loop and routes actions to sub-modules.
    """
    def __init__(self):
        self.console = Console()
        self.running = True
        self.menu = MainMenu()
        
        # PERFORMANCE FIX: Eagerly instantiate all major modules once.
        # This prevents costly re-initialization (e.g., re-initializing YahooWrapper
        # and its large caches) every time the user returns to the main menu.
        self.market_feed = MarketFeed()
        self.client_manager = ClientManager()
        self.settings_module = SettingsModule()

    def run(self):
        """The Main Event Loop."""

        while self.running:
            # 1. Display Menu & Get Action
            try:
                action = self.menu.display()
                # 2. Route Action
                self.handle_action(action)
            except MainMenuRequested:
                continue

    def handle_action(self, action: str):
        """Routing Logic"""
        
        if action == "exit":
            self.shutdown()
        
        elif action == "client_mgr":
            # Use the already initialized instance
            self.client_manager.run()
            
        elif action == "market_data":
            # Use the already initialized instance
            self.market_feed.run()

        elif action == "intel_reports":
            self.market_feed.run_intel_reports()

        elif action == "global_trackers":
            self.market_feed.run_global_trackers()

        elif action == "fin_tools":
            self.placeholder_module("Financial Math Toolkit")
            
        elif action == "settings":
            # Use the already initialized instance
            self.settings_module.run()

    # Using this as temp page when adding new modules
    def placeholder_module(self, name: str):
        self.console.print(f"\n[bold green]>> LOADING {name}...[/bold green]")
        self.console.print("[italic]   Module logic to be implemented soon ...[/italic]")
        InputSafe.pause()

    def shutdown(self):
        self.console.print("\n[bold red]>> Closing Session...[/bold red]")
        self.console.print("[dim]   Data saved.\n   Connections terminated.\n   Logs cleared from terminal.[/dim]\n")
        sys.exit(0)
