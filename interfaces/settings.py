import sys
import os
import time
import shutil
import socket
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from utils.input import InputSafe
from utils.text_fx import TextEffectManager
from utils.system import SystemHost 
from utils.charts import ChartRenderer

class SettingsModule:
    def __init__(self):
        self.console = Console()
        self.text_fx = TextEffectManager()
        
        self.settings = {
            "display": {"theme": "default", "color_highlight": "blue", "show_animations": True},
            "network": {"refresh_interval": 60, "timeout": 5, "retries": 3},
            "system": {"cache_size_mb": 512, "log_level": "INFO"}
        }

    # --- 1. API & Security ---
    def _menu_api_security(self):
        while True:
            self.console.clear()
            
            # Modular Menu Definition
            options = {
                "1": "Update Finnhub API Key",
                "2": "Update SMTP/Email Credentials",
                "3": "Clear All Stored Credentials",
                "0": "Back"
            }
            
            InputSafe.display_options(options, title="🔒 API & SECURITY SETTINGS")
            choice = InputSafe.get_option(list(options.keys())) # Uses default [>] prompt
            
            if choice == "0": break
            if choice == "1": self._update_finnhub_key()
            if choice == "2": self._update_smtp_creds()
            if choice == "3": self._clear_credentials()

    def _update_finnhub_key(self):
        self.console.print("\n--- [bold]Update Finnhub Key[/bold] ---")
        new_key = InputSafe.get_string("Enter new API Key (leave empty to cancel)")
        if not new_key: return

        env_path = os.path.join(os.getcwd(), ".env")
        try:
            lines = []
            if os.path.exists(env_path):
                with open(env_path, 'r') as f: lines = f.readlines()
            
            with open(env_path, 'w') as f:
                key_written = False
                for line in lines:
                    if line.startswith("FINNHUB_API_KEY="):
                        f.write(f"FINNHUB_API_KEY={new_key}\n")
                        key_written = True
                    else:
                        f.write(line)
                if not key_written:
                    if lines and not lines[-1].endswith('\n'): f.write('\n')
                    f.write(f"FINNHUB_API_KEY={new_key}\n")
            
            os.environ["FINNHUB_API_KEY"] = new_key
            self.console.print("[green]Key updated successfully.[/green]")
        except Exception as e:
            self.console.print(f"[red]Error saving key: {e}[/red]")
        InputSafe.pause()

    def _update_smtp_creds(self):
        self.console.print("\n[dim]Feature: SMTP Configuration[/dim]")
        email = InputSafe.get_string("Enter Sender Email:")
        self.console.print(f"[yellow]Stored email '{email}' to session config (dummy).[/yellow]")
        InputSafe.pause()

    def _clear_credentials(self):
        if InputSafe.get_yes_no("Are you sure you want to clear ALL cached keys?"):
            os.environ.pop("FINNHUB_API_KEY", None)
            self.console.print("[red]Credentials cleared from active session.[/red]")
        InputSafe.pause()


    # --- 2. Display & UX ---
    def _menu_display_ux(self):
        while True:
            self.console.clear()
            
            # Dynamic options based on current settings
            hl = self.settings['display']['color_highlight']
            anim = self.settings['display']['show_animations']
            
            options = {
                "1": f"Highlight Color (Current: [bold {hl}]{hl}[/])",
                "2": f"UI Animations (Current: {anim})",
                "0": "Back"
            }
            
            InputSafe.display_options(options, title="🎨 DISPLAY & UX SETTINGS")
            choice = InputSafe.get_option(list(options.keys()))
            
            if choice == "0": break
            if choice == "1":
                c = InputSafe.get_string("Enter color (blue, green, magenta, gold1):")
                if c: self.settings['display']['color_highlight'] = c
            if choice == "2":
                self.settings['display']['show_animations'] = not self.settings['display']['show_animations']


    # --- 3. System & Performance ---
    def _menu_system_perf(self):
        while True:
            self.console.clear()
            
            net = self.settings['network']
            sys_conf = self.settings['system']
            
            options = {
                "1": f"Data Refresh Interval: [bold]{net['refresh_interval']}s[/bold]",
                "2": f"API Request Timeout: [bold]{net['timeout']}s[/bold]",
                "3": f"Max Cache Size: [bold]{sys_conf['cache_size_mb']} MB[/bold]",
                "0": "Back"
            }

            InputSafe.display_options(options, title="⚡ SYSTEM & PERFORMANCE")
            choice = InputSafe.get_option(list(options.keys()))
            
            if choice == "0": break
            if choice == "1":
                val = InputSafe.get_float("Enter seconds (10-3600):", 10, 3600)
                self.settings['network']['refresh_interval'] = int(val)
            if choice == "2":
                val = InputSafe.get_float("Enter seconds (1-60):", 1, 60)
                self.settings['network']['timeout'] = int(val)
            if choice == "3":
                val = InputSafe.get_float("Enter MB (1-1024):", 1, 1024)
                self.settings['system']['cache_size_mb'] = int(val)

    # --- 4. Deep Diagnostics (Unchanged logic, just standard prompt) ---
    def _run_deep_diagnostics(self):
        self.console.clear()
        self.console.print("\n[bold]🩺 DEEP SYSTEM DIAGNOSTICS[/bold]")
        
        results = {}
        with self.console.status("[bold cyan]Testing Connectivity...[/bold cyan]"):
            try:
                start = time.time()
                socket.gethostbyname("google.com")
                dns_time = (time.time() - start) * 1000
                results['dns'] = f"{dns_time:.1f}ms"
                results['net_status'] = True
            except:
                results['dns'] = "FAIL"
                results['net_status'] = False

        total, used, free = shutil.disk_usage("/")
        disk_percent = (used / total) * 100
        results['disk_usage'] = disk_percent
        sys_info = SystemHost.get_info()
        
        self.console.print("\n[bold white]DIAGNOSTIC REPORT[/bold white]")
        table = Table(box=box.SIMPLE)
        table.add_column("Metric", style="dim")
        table.add_column("Value/Status", justify="left")
        table.add_column("Visual", width=20)

        net_icon = ChartRenderer.get_status_icon(results['net_status'])
        table.add_row("Network (DNS)", str(results['dns']), net_icon)
        
        disk_bar = ChartRenderer.generate_usage_bar(results['disk_usage'])
        table.add_row("Disk Usage", f"{results['disk_usage']:.1f}%", disk_bar)

        try:
            cpu_val = float(sys_info['cpu_usage'].strip('%'))
            cpu_bar = ChartRenderer.generate_usage_bar(cpu_val)
        except:
            cpu_val = 0
            cpu_bar = Text("Error")
        table.add_row("CPU Load", sys_info['cpu_usage'], cpu_bar)
        
        try:
            mem_str = sys_info['mem_usage'].split('%')[0]
            mem_val = float(mem_str)
            mem_bar = ChartRenderer.generate_usage_bar(mem_val)
        except:
            mem_bar = Text("N/A")    
        table.add_row("Memory Load", sys_info['mem_usage'], mem_bar)

        self.console.print(table)
        InputSafe.pause()

    # --- Panel Builder (Unchanged) ---
    def _build_info_panel(self) -> Panel:
        try: data = SystemHost.get_info()
        except: data = {"hostname": "Unknown", "ip": "0.0.0.0", "cpu_usage": "0%", "mem_usage": "0%", "finnhub_status": False}

        try: cpu_p = float(data['cpu_usage'].strip('%'))
        except: cpu_p = 0.0
        try: mem_p = float(data['mem_usage'].split('%')[0])
        except: mem_p = 0.0

        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)

        left_table = Table.grid(padding=(0,1))
        left_table.add_column(style="bold cyan", width=12)
        left_table.add_column(style="white")
        left_table.add_row("USER:", str(data.get('user', 'N/A')))
        left_table.add_row("HOST:", str(data.get('hostname', 'N/A')))
        left_table.add_row("IP:", str(data.get('ip', 'N/A')))
        left_table.add_row("OS:", str(data.get('os', 'N/A')))
        
        finnhub_status = "ACTIVE" if data['finnhub_status'] else "MISSING"
        finnhub_style = "bold green" if data['finnhub_status'] else "bold red"
        left_table.add_row("API KEY:", f"[{finnhub_style}]{finnhub_status}[/{finnhub_style}]")

        right_table = Table.grid(padding=(0,1))
        right_table.add_column(style="bold magenta", width=10)
        right_table.add_column(width=20)
        right_table.add_column(width=8, justify="right")
        cpu_bar = ChartRenderer.generate_usage_bar(cpu_p, width=15)
        right_table.add_row("CPU", cpu_bar, f"{cpu_p:.1f}%")
        mem_bar = ChartRenderer.generate_usage_bar(mem_p, width=15)
        right_table.add_row("RAM", mem_bar, f"{mem_p:.1f}%")
        right_table.add_row("PYTHON", "", data.get('python_version', '?'))

        grid.add_row(
            Panel(left_table, title="Identity", border_style="bold cyan", box=box.SIMPLE),
            Panel(right_table, title="Resources", border_style="magenta", box=box.SIMPLE)
        )

        return Panel(
            grid,
            box=box.ROUNDED,
            border_style=self.settings['display']['color_highlight'],
            title="[bold]Settings[/bold]",
        )

    # --- Main Loop ---
    def run(self):
        while True:
            self.console.clear()
            self.console.print(self._build_info_panel())
            
            # Modular Menu Implementation
            options = {
                "1": "🔒 API & Security",
                "2": "🎨 Display & UX",
                "3": "⚡ System & Performance",
                "4": "🩺 Run Quick Diagnostics",
                "0": "🔙 Return to Main"
            }
            
            # Using the centralized renderer
            InputSafe.display_options(options)
            
            # Using default prompt from get_option which is now [>]
            choice = InputSafe.get_option(list(options.keys()))

            if choice == "0": break
            elif choice == "1": self._menu_api_security()
            elif choice == "2": self._menu_display_ux()
            elif choice == "3": self._menu_system_perf()
            elif choice == "4": self._run_deep_diagnostics()