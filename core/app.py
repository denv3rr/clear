import sys
from rich.console import Console

# Import internal modudles
from interfaces.menus import MainMenu
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

    def run(self):
        """The Main Event Loop."""
        
        while self.running:
            # 1. Display Menu & Get Action (Let's fuckin go)
            action = self.menu.display()

            # 2. Route Action
            self.handle_action(action)

    def handle_action(self, action: str):
        """Routing Logic"""
        
        if action == "exit":
            self.shutdown()
        
        elif action == "client_mgr":
            mgr = ClientManager()
            mgr.run()
            
        elif action == "market_data":
            feed = MarketFeed()
            feed.run()
            
        elif action == "fin_tools":
            self.placeholder_module("Financial Math Toolkit")
            
        elif action == "settings":
            settings = SettingsModule()
            settings.run()

    # Using this as temp page when adding new modules
    def placeholder_module(self, name: str):
        self.console.print(f"\n[bold green]>> LOADING {name}...[/bold green]")
        self.console.print("[italic]   Module logic to be implemented soon ...[/italic]")
        InputSafe.pause()

    def shutdown(self):
        self.console.print("\n[bold red]>> Closing Session...[/bold red]")
        self.console.print("[dim]   Data saved.\n   Connections terminated.\n   Logs cleared from terminal.[/dim]\n")
        sys.exit(0)