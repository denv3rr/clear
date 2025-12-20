# interfaces/navigator.py
import sys
import os
from rich.console import Console
from utils.input import InputSafe

class Navigator:
    """
    Standardized Menu Controller.
    Injects global navigation options (Main Menu, Exit) into local context menus.
    """
    console = Console()

    @staticmethod
    def show_options(local_options: dict, title: str = "ACTIONS", auto_clear: bool = False) -> str:
        """
        Displays a menu with Local options + Global options (Main Menu, Exit).
        Returns the key selected by the user.
        """
        if auto_clear:
            Navigator.clear()

        # 1. Standard Global Options
        global_opts = {
            "M": "🏠 Main Menu",
            "X": "❌ Exit Application"
        }

        # 2. Merge options (Locals first)
        # We merge them so InputSafe formats them identically (e.g. [1], [M])
        combined_options = {**local_options, **global_opts}

        # 3. Display & Get Input
        InputSafe.display_options(combined_options, title=title)
        
        # Helper to get valid keys including case-insensitivity
        choice = InputSafe.get_option(list(combined_options.keys()), prompt_text="[>]").upper()

        # 4. Handle Global Actions Immediately
        if choice == "X":
            Navigator.exit_app()
        if choice == "M":
            return "MAIN_MENU"
            
        return choice

    @staticmethod
    def exit_app():
        Navigator.console.print("\n[bold red]>> Exiting Application...[/bold red]")
        sys.exit(0)

    @staticmethod
    def clear():
        """Cross-platform console clear."""
        if os.name == 'nt': _ = os.system('cls')
        else: _ = os.system('clear')
        print("\x1b[3J", end="") # Clear scrollback buffer