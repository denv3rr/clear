import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box

from utils.input import InputSafe
from utils.text_fx import TextEffectManager
from utils.system import SystemHost

class SettingsModule:
    def __init__(self):
        self.console = Console()
        self.text_fx = TextEffectManager()

    def _build_info_panel(self) -> Panel:
        """Helper to build and return the main status info panel."""
        try:
            data = SystemHost.get_info()
        except:
            data = {
                "hostname": "Unknown", "user": "User", "os": "Unknown", 
                "ip": "0.0.0.0", "login_time": "Now", "finnhub_status": False
            }

        grid = Table.grid(expand=True)
        grid.add_column(justify="left", width=25)
        grid.add_column(justify="left")

        grid.add_row(f"[bold cyan]HOSTNAME:[/bold cyan]", f"{data['hostname']}")
        grid.add_row(f"[bold cyan]USER:[/bold cyan]", f"{data['user']}")
        grid.add_row(f"[bold cyan]OS:[/bold cyan]", f"{data['os']}")
        grid.add_row(f"[bold cyan]LOCAL IP:[/bold cyan]", f"{data['ip']}")

        color = "green" if data["finnhub_status"] else "red"
        status = "DETECTED" if data["finnhub_status"] else "MISSING"

        grid.add_row("")
        grid.add_row(f"[bold white]SYSTEM TIME:[/bold white]", f"{data['login_time']}")
        grid.add_row(f"[bold white]FINNHUB KEY:[/bold white]", f"[{color}]{status}[/{color}]")

        info_panel = Panel(
            Align.center(grid, vertical="middle"),
            box=box.SIMPLE,
            border_style="blue",
            title="[bold blue]SYSTEM & API STATUS[/bold blue]",
            padding=(1, 2)
        )
        return info_panel

    def run(self):
        """Main loop for the settings module."""
        while True:
            self.console.clear()
            
            # 1. Build and Animate the top info panel (Thunderstorm)
            info_panel = self._build_info_panel()
            self.console.print(info_panel)

            # 2. Display Settings Options (Placeholders)
            self.console.print("\n[bold gold1]SETTINGS:[/bold gold1]")
            self.console.print("[1] 🔑 Update Finnhub API Key")
            self.console.print("[2] 📝 Change User Preferences")
            self.console.print("[0] 🔙 Return to Main Menu")
            
            choice = InputSafe.get_option(["1", "2", "0"], prompt_text="SELECT OPTION >")
            
            if choice == "0":
                self.console.clear()
                break
            elif choice == "1":
                self.console.print("[dim]Not yet implemented: API Key Update...[/dim]")
                InputSafe.pause()
            elif choice == "2":
                self.console.print("[dim]Not yet implemented: Preferences...[/dim]")
                InputSafe.pause()