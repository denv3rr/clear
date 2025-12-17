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
            # Structure to include all keys returned by SystemHost
            data = {
                "hostname": "Unknown",
                "user": "User",
                "os": "Unknown",
                "ip": "0.0.0.0",
                "login_time": "Now",
                "finnhub_status": False,
                "cpu_usage": "N/A",
                "mem_usage": "N/A",
                "cpu_cores": "N/A",
                "python_version": "N/A",
            }

        # --- 1. ASCII Art ---
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
        info_panel_content.add_row(f"")

        # LINKS IN GRID
        links_grid = Table.grid(expand=False, padding=(0, 1))
        links_grid.add_column(style="blue", justify="left", ratio=1)
        links_grid.add_column(style="white", justify="left", ratio=1)

        links_grid.add_row("PROJECT REPO:", 
                           "https://github.com/denv3rr/clear")
        links_grid.add_row("DOCUMENTATION:", 
                           "https://github.com/denv3rr/clear/blob/main/README.md")
        links_grid.add_row("FINNHUB REGISTER:", 
                           "https://finnhub.io/register")
        links_grid.add_row("FINNHUB DASHBOARD:", 
                           "https://finnhub.io/dashboard")

        invisible_link_wrapper = Panel(
            Align.center(links_grid),
            box=box.SIMPLE,
            border_style="",
            padding=(0, 0),
        )

        info_panel_content.add_row(invisible_link_wrapper)

        info_panel = Panel(
            info_panel_content,
            box=box.ROUNDED,
            border_style="blue",
            padding=(1, 3),
            width=100,
        )

        # --- 3. System Info Grid (Outer Table - holds all sys info) ---
        sys_info_grid_content = Table.grid(expand=True, padding=(0, 0))
        sys_info_grid_content.add_column(justify="left") 

        # Metrics Grid
        two_col_metrics_grid = Table.grid(expand=True, padding=(0, 0))
        # Column for Host/OS
        two_col_metrics_grid.add_column(justify="left", ratio=1) 
        # Column for Hardware/Python
        two_col_metrics_grid.add_column(justify="left", ratio=1) 

        # Inner table for Host/OS (Left Column - 4 rows)
        left_col = Table.grid(padding=(0, 2))
        left_col.add_column(style="bold cyan", min_width=12, justify="left")
        left_col.add_column(style="white", justify="left")
        
        left_col.add_row("[+] HOSTNAME:", data['hostname'])
        left_col.add_row("[+] USER:", data['user'])
        left_col.add_row("[+] OS:", data['os'])
        left_col.add_row("[+] LOCAL IP:", data['ip'])
        
        # Inner table for Hardware/Python (Right Column - 4 rows)
        right_col = Table.grid(padding=(0, 2))
        right_col.add_column(style="bold cyan", min_width=12, justify="left")
        right_col.add_column(style="white", justify="left")
        
        right_col.add_row("[+] PYTHON:", data.get('python_version', 'N/A'))
        right_col.add_row("[+] CPU CORES:", str(data.get('cpu_cores', 'N/A')))
        right_col.add_row("[+] CPU USAGE:", data.get('cpu_usage', 'N/A'))
        right_col.add_row("[+] RAM USAGE:", data.get('mem_usage', 'N/A'))
        
        # 2 inner tables added to the 2-column grid
        two_col_metrics_grid.add_row(left_col, right_col)

        # 2-column grid to the main sys_info_grid_content
        sys_info_grid_content.add_row(two_col_metrics_grid)

        # Final status lines at the bottom
        color = "green" if data["finnhub_status"] else "red"
        status = "DETECTED" if data["finnhub_status"] else "MISSING"

        sys_info_grid_content.add_row("")
        sys_info_grid_content.add_row(f"[bold cyan][+][/bold cyan] [bold cyan]SYSTEM TIME: [/bold cyan]  {data['login_time']}")
        sys_info_grid_content.add_row(f"[bold cyan][+][/bold cyan] [bold cyan]FINNHUB KEY: [/bold cyan]  [{color}]{status}[/{color}]")

        sys_info_grid = Panel(
            sys_info_grid_content,
            box=box.ROUNDED,
            border_style="blue",
            padding=(1, 3),
            width=100,
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
        # Row 2: Centered Info Panel
        main_layout_grid.add_row(Align.center(info_panel)) 

        # Row 3: Centered System Info Grid (now with two columns inside)
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