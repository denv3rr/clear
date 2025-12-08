import sys
from rich.console import Console

# Import Interfaces
from interfaces.menus import MainMenu
from utils.input import InputSafe

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
            # 1. Display Menu & Get Action
            action = self.menu.display()

            # 2. Route Action
            self.handle_action(action)

    def handle_action(self, action: str):
        """Routing Logic"""
        
        if action == "exit":
            self.shutdown()
        
        elif action == "client_mgr":
            self.placeholder_module("Client Management")
            
        elif action == "market_data":
            self.placeholder_module("Market Data & Futures")
            
        elif action == "fin_tools":
            self.placeholder_module("Financial Math Toolkit")
            
        elif action == "settings":
            self.placeholder_module("System Settings")

    def placeholder_module(self, name: str):
        """Temporary stub for modules we haven't built yet."""
        self.console.print(f"\n[bold green]>> LOADING MODULE: {name}...[/bold green]")
        self.console.print("[italic]... Module logic to be implemented soon ...[/italic]")
        InputSafe.pause()

    def shutdown(self):
        """Clean exit procedure."""
        self.console.print("\n[bold red]>> Closing Secure Session...[/bold red]")
        self.console.print("[dim]   Data saved. Connections terminated.[/dim]\n")
        sys.exit(0)