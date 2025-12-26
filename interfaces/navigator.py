# interfaces/navigator.py
import sys
import os
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich import box
from utils.input import InputSafe
from interfaces.shell import ShellRenderer

class Navigator:
    """
    Standardized Menu Controller.
    Injects global navigation options (Main Menu, Exit) into local context menus.
    """
    console = Console()

    @staticmethod
    def show_options(local_options: dict, title: str = "ACTIONS", auto_clear: bool = False, show_menu: bool = True) -> str:
        """
        Displays a menu with Local options + Global options (Main Menu, Exit).
        Returns the key selected by the user.
        """
        if auto_clear:
            Navigator.clear()

        # 1. Standard Global Options
        global_opts = {
            "M": "Main Menu",
            "X": "Exit Application"
        }

        # 2. Merge options (Locals first)
        # We merge them so InputSafe formats them identically (e.g. [1], [M])
        combined_options = {**local_options, **global_opts}

        # 3. Display & Get Input (ShellRenderer selector)
        table = Table.grid(padding=(0, 1))
        table.add_column()
        if show_menu:
            for key, label in combined_options.items():
                table.add_row(f"[bold cyan]{key}[/bold cyan]  {label}")
        else:
            table.add_row("[dim]Select an option[/dim]")
        panel = Panel(table, title=title, border_style="cyan", box=box.ROUNDED)
        choice = ShellRenderer.render_and_prompt(
            Group(panel),
            context_actions=combined_options,
            valid_choices=list(combined_options.keys()) + ["m", "x"],
            prompt_label=">",
            show_main=False,
            show_back=False,
            show_exit=False,
            show_header=False,
        ).upper()

        # 4. Handle Global Actions Immediately
        if choice == "X":
            Navigator.exit_app()
        if choice == "M":
            return "MAIN_MENU"
            
        return choice

    @staticmethod
    def exit_app():
        if InputSafe.get_yes_no("Exit application?"):
            Navigator.console.print("\n[bold red]>> Exiting Application...[/bold red]")
            sys.exit(0)

    @staticmethod
    def clear():
        """Cross-platform console clear."""
        if os.name == 'nt': _ = os.system('cls')
        else: _ = os.system('clear')
        print("\x1b[3J", end="") # Clear scrollback buffer
