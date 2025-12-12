import time
import os
os.environ["TTE_DEBUG"] = "0"

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.align import Align
from rich.rule import Rule

from utils.system import SystemHost
from utils.text_fx import TextEffectManager

class StartupScreen:
    def __init__(self, movement_speed: float = 1):
        self.console = Console()
        self.speed = movement_speed
        self.text_fx_manager = TextEffectManager(movement_speed)

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

        # --- 1. ASCII Art Content (Raw String) ---
        # Extracted directly from the snippet's content
        ascii_art_clear = r"""
 ██████╗██╗     ███████╗ █████╗ ██████╗ 
██╔════╝██║     ██╔════╝██╔══██╗██╔══██╗
██║     ██║     █████╗  ███████║██████╔╝
██║     ██║     ██╔══╝  ██╔══██║██╔══██╗
╚██████╗███████╗███████╗██║  ██║██║  ██║
 ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝
"""

        ascii_art_divider = r"""
█████╗█████╗█████╗█████╗█████╗█████╗█████╗█████╗█████╗█████╗█████╗█████╗
╚════╝╚════╝╚════╝╚════╝╚════╝╚════╝╚════╝╚════╝╚════╝╚════╝╚════╝╚════╝
"""

        ascii_art_dash = r"""
█████╗
╚════╝
"""
        
        # --- 2. Info Panel Content (Centered, with outline) ---
        info_panel_content = Table.grid(expand=True, padding=(0, 0))
        info_panel_content.add_column(justify="center")

        info_panel_content.add_row(f"[bold white]Welcome, {data['user']}.[/bold white]")
        info_panel_content.add_row(f"[yellow]{ascii_art_dash}[/yellow]")

        # LINKS IN GRID
        links_grid = Table.grid(expand=False, padding=(0, 1))
        links_grid.add_column(justify="left", ratio=1)
        links_grid.add_column(justify="left", ratio=1)

        links_grid.add_row("[yellow]PROJECT REPO:[/yellow]", 
                           "https://github.com/denv3rr/clear")
        links_grid.add_row("[yellow]DOCUMENTATION:[/yellow]", 
                           "https://github.com/denv3rr/clear/blob/main/README.md")
        links_grid.add_row("[yellow]FINNHUB REGISTER:[/yellow]", 
                           "https://finnhub.io/register")
        links_grid.add_row("[yellow]FINNHUB DASHBOARD:[/yellow]", 
                           "https://finnhub.io/dashboard")

        info_panel_content.add_row(links_grid)

        info_panel = Panel(
            info_panel_content,
            box=box.ROUNDED,
            border_style="yellow",
            padding=(1, 3),
        )

        # --- 3. System Info Grid (Left justified content inside the column) ---
        sys_info_grid_content = Table.grid(expand=True, padding=(0, 0))
        # This column is left-justified, as required:
        sys_info_grid_content.add_column(justify="left") 

        sys_info_grid_content.add_row(f"[bold cyan][+] HOSTNAME:[/bold cyan] {data['hostname']}")
        sys_info_grid_content.add_row(f"[bold cyan][+] USER:[/bold cyan]     {data['user']}")
        sys_info_grid_content.add_row(f"[bold cyan][+] OS:[/bold cyan]       {data['os']}")
        sys_info_grid_content.add_row(f"[bold cyan][+] LOCAL IP:[/bold cyan] {data['ip']}")

        color = "green" if data["finnhub_status"] else "red"
        status = "DETECTED" if data["finnhub_status"] else "MISSING"

        sys_info_grid_content.add_row("")
        sys_info_grid_content.add_row(f"[bold white]SYSTEM TIME:[/bold white]  {data['login_time']}")
        sys_info_grid_content.add_row(f"[bold white]FINNHUB KEY:[/bold white]  [{color}]{status}[/{color}]")

        sys_info_grid = Panel(
            sys_info_grid_content,
            box=box.ROUNDED,
            border_style="yellow",
            padding=(1, 3),
        )

        # --- 4. Main Layout Grid (Three Rows for vertical arrangement) ---
        # This grid ensures all components are centered horizontally.
        main_layout_grid = Table.grid(expand=True)
        main_layout_grid.add_column(justify="center", ratio=1) 

        # Row 1: Centered ASCII Art
        main_layout_grid.add_row(Align.center("[warning]⚠  WORK IN PROGRESS ⚠[/warning]"))
        main_layout_grid.add_row(Align.center(ascii_art_clear))
        main_layout_grid.add_row(Align.center("[blue]Prices. Books. Analysis.[/blue]"))
        
        main_layout_grid.add_row(Align.center(ascii_art_divider))
        # Row 2: NEW Centered Info Panel
        main_layout_grid.add_row(Align.center(info_panel)) 

        # Row 3: Centered System Info Grid (which contains left-justified text)
        main_layout_grid.add_row(Align.center(sys_info_grid))
        main_layout_grid.add_row(Align.center(ascii_art_divider))

        # --- 5. Encapsulate in a Rich panel with fixed width 200 ---
        panel = Panel(
            main_layout_grid, 
            box=box.ROUNDED,
            border_style="blue",
            title="[bold gold1]https://seperet.com[/bold gold1]",
            padding=(1, 3),
            width=200
        )

        # UNCOMMENT THESE 2 LINES TO ENABLE TEXT EFFECTS AT OPENING:
        # text_content = self.text_fx_manager._panel_to_text(Align.center(panel))
        # self.text_fx_manager.play_smoke(text_content)

        # THEN COMMENT THIS OUT (OR YOU WILL GET DOUBLE OUTPUT):
        self.console.print(Align.center(panel))