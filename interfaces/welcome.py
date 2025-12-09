import time
import os
os.environ["TTE_DEBUG"] = "0"

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.align import Align

from utils.system import SystemHost
from utils.text_fx import TextEffectManager

class StartupScreen:
    def __init__(self, movement_speed: float = 200):
        self.console = Console()
        self.speed = movement_speed  # Frames per second
        self.text_fx_manager = TextEffectManager(movement_speed) # Manager initialized

    def render(self):
        try:
            data = SystemHost.get_info()
        except:
            data = {
                "hostname": "Unknown",
                "user": "User",
                "os": "Unknown",
                "ip": "0.0.0.0",
                "login_time": "Now",
                "finnhub_status": False
            }

        # Build table with system information
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")

        grid.add_row(f"[bold cyan][+] HOSTNAME:[/bold cyan] {data['hostname']}")
        grid.add_row(f"[bold cyan][+] USER:[/bold cyan]     {data['user']}")
        grid.add_row(f"[bold cyan][+] OS:[/bold cyan]       {data['os']}")
        grid.add_row(f"[bold cyan][+] LOCAL IP:[/bold cyan] {data['ip']}")

        color = "green" if data["finnhub_status"] else "red"
        status = "DETECTED" if data["finnhub_status"] else "MISSING"

        grid.add_row("")
        grid.add_row(f"[bold white]SYSTEM TIME:[/bold white] {data['login_time']}")
        grid.add_row(f"[bold white]FINNHUB KEY:[/bold white] [{color}]{status}[/{color}]")

        # Encapsulate in a Rich panel
        panel = Panel(
            Align.center(grid, vertical="middle"),
            box=box.ROUNDED,
            border_style="blue",
            title="[bold gold1]CLEAR[/bold gold1]",
            padding=(1, 2)
        )

        self.console.clear()

        # -------- INTRO --------
        self.text_fx_manager.play_smoke(panel)