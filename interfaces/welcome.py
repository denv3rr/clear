from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.align import Align
from utils.system import SystemHost

class StartupScreen:
    def __init__(self):
        self.console = Console()
    
    def render(self):
        """Fetches system data and renders the boot screen."""
        try:
            sys_data = SystemHost.get_info()
        except Exception as e:
            # Fallback if system.py fails
            sys_data = {
                "hostname": "Unknown",
                "user": "User",
                "os": "Unknown",
                "ip": "0.0.0.0",
                "login_time": "Now",
                "finnhub_status": False
            }

        # Create the inner table for layout
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)

        # Left Side Data
        grid.add_row(f"[bold cyan][+] HOSTNAME:[/bold cyan] {sys_data['hostname']}")
        grid.add_row(f"[bold cyan][+] USER:[/bold cyan]     {sys_data['user']}")
        grid.add_row(f"[bold cyan][+] OS:[/bold cyan]       {sys_data['os']}")
        grid.add_row(f"[bold cyan][+] LOCAL IP:[/bold cyan] {sys_data['ip']}")
        
        # Status Checks (Right Side)
        api_color = "green" if sys_data['finnhub_status'] else "red"
        api_text = "DETECTED" if sys_data['finnhub_status'] else "MISSING"
        
        grid.add_row(" ") # Spacer
        grid.add_row(f"[bold white]SYSTEM TIME:[/bold white] {sys_data['login_time']}")
        grid.add_row(f"[bold white]FINNHUB KEY:[/bold white] [{api_color}]{api_text}[/{api_color}]")

        # The Main Panel
        panel = Panel(
            Align.center(grid, vertical="middle"),
            box=box.ROUNDED,
            title="[bold gold1]CLEAR[/bold gold1]",
            subtitle="[italic grey70]Secure Advisory Terminal[/italic grey70]",
            border_style="blue",
            padding=(1, 2)
        )

        self.console.clear()
        self.console.print(panel)
        self.console.print("[italic grey70]https://seperet.com[/italic grey70]\n\n[dim]Initializing Modules...[/dim]", justify="center")
        
        # Pause for effect
        input("\n   >>> Press ENTER")