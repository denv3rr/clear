import sys
import os
import time
import shutil
import socket
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.console import Group

from utils.input import InputSafe
from utils.text_fx import TextEffectManager
from utils.system import SystemHost 
from utils.charts import ChartRenderer
from interfaces.shell import ShellRenderer
from interfaces.navigator import Navigator

class SettingsModule:
    def __init__(self):
        self.console = Console()
        self.text_fx = TextEffectManager()

        self.settings_file = os.path.join(os.getcwd(), "config", "settings.json")
        self.settings = self._load_settings()
        stored_key = self.settings.get("credentials", {}).get("finnhub_key")
        if stored_key and not os.getenv("FINNHUB_API_KEY"):
            os.environ["FINNHUB_API_KEY"] = stored_key

    def _default_settings(self):
        return {
            "display": {"theme": "default", "color_highlight": "blue", "show_animations": True},
            "network": {"refresh_interval": 60, "timeout": 5, "retries": 3},
            "system": {"cache_size_mb": 512, "log_level": "INFO"},
            "credentials": {"smtp": {}, "finnhub_key": ""}
        }

    def _load_settings(self):
        defaults = self._default_settings()
        if not os.path.exists(self.settings_file):
            return defaults
        try:
            with open(self.settings_file, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return defaults
            # Shallow merge defaults
            for k, v in defaults.items():
                if k not in data or not isinstance(data.get(k), dict):
                    data[k] = v
            return data
        except Exception:
            return defaults

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            self.console.print(f"[red]Error saving settings: {e}[/red]")

    # --- 1. API & Security ---
    def _menu_api_security(self):
        while True:
            # Context actions
            options = {
                "1": "Update Finnhub API Key",
                "2": "Update SMTP/Email Credentials",
                "3": "Clear All Stored Credentials",
                "4": "View Stored Credential Status",
                "0": "Back"
            }
            
            status = Table(box=box.SIMPLE, show_header=False)
            status.add_column("Field", style="bold cyan")
            status.add_column("Value", justify="right")
            status.add_row("Finnhub Key", "SET" if os.getenv("FINNHUB_API_KEY") else "MISSING")
            status.add_row("SMTP Profile", "SET" if self.settings.get("credentials", {}).get("smtp") else "MISSING")
            panel = Panel(status, title="🔒 API & SECURITY SETTINGS", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label="[>]",
                show_main=True,
                show_back=True,
                show_exit=True,
            )
            
            if choice == "0": break
            if choice == "m": break
            if choice == "x": Navigator.exit_app()
            if choice == "1": self._update_finnhub_key()
            if choice == "2": self._update_smtp_creds()
            if choice == "3": self._clear_credentials()
            if choice == "4": self._show_credential_status()

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
            self.settings["credentials"]["finnhub_key"] = new_key
            self._save_settings()
            self.console.print("[green]Key updated successfully.[/green]")
        except Exception as e:
            self.console.print(f"[red]Error saving key: {e}[/red]")
        InputSafe.pause()

    def _update_smtp_creds(self):
        self.console.print("\n--- [bold]SMTP Configuration[/bold] ---")
        host = InputSafe.get_string("SMTP Host (leave empty to cancel):")
        if not host:
            return
        port = InputSafe.get_float("SMTP Port:", min_val=1, max_val=65535)
        username = InputSafe.get_string("SMTP Username:")
        sender = InputSafe.get_string("Sender Email:")
        use_tls = InputSafe.get_yes_no("Use TLS?")
        password = InputSafe.get_string("SMTP Password (stored in settings file):")

        self.settings["credentials"]["smtp"] = {
            "host": host,
            "port": int(port),
            "username": username,
            "sender": sender,
            "use_tls": bool(use_tls),
            "password": password,
        }
        self._save_settings()
        self.console.print("[green]SMTP credentials saved.[/green]")
        InputSafe.pause()

    def _clear_credentials(self):
        if InputSafe.get_yes_no("Are you sure you want to clear ALL cached keys?"):
            os.environ.pop("FINNHUB_API_KEY", None)
            self.settings["credentials"] = {"smtp": {}, "finnhub_key": ""}
            self._save_settings()
            self.console.print("[red]Credentials cleared from active session.[/red]")
        InputSafe.pause()

    def _show_credential_status(self):
        self.console.print("\n--- [bold]Credential Status[/bold] ---")
        finnhub_set = bool(self.settings.get("credentials", {}).get("finnhub_key"))
        smtp_set = bool(self.settings.get("credentials", {}).get("smtp"))
        self.console.print(f"Finnhub Key: {'SET' if finnhub_set else 'MISSING'}")
        self.console.print(f"SMTP Profile: {'SET' if smtp_set else 'MISSING'}")
        InputSafe.pause()

    # --- 2. Display & UX ---
    def _menu_display_ux(self):
        while True:
            hl = self.settings['display']['color_highlight']
            anim = self.settings['display']['show_animations']
            
            # Context actions
            options = {
                "1": f"Highlight Color (Current: [bold {hl}]{hl}[/])",
                "2": f"UI Animations (Current: {anim})",
                "0": "Back"
            }
            
            status = Table(box=box.SIMPLE, show_header=False)
            status.add_column("Field", style="bold cyan")
            status.add_column("Value", justify="right")
            status.add_row("Highlight Color", hl)
            status.add_row("Animations", str(anim))
            panel = Panel(status, title="🎨 DISPLAY & UX SETTINGS", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label="[>]",
                show_main=True,
                show_back=True,
                show_exit=True,
            )
            
            if choice == "0": break
            if choice == "m": break
            if choice == "x": Navigator.exit_app()
            if choice == "1":
                c = InputSafe.get_string("Enter color (blue, green, magenta, gold1):")
                if c: self.settings['display']['color_highlight'] = c
            if choice == "2":
                self.settings['display']['show_animations'] = not self.settings['display']['show_animations']
            self._save_settings()


    # --- 3. System & Performance ---
    def _menu_system_perf(self):
        while True:
            net = self.settings['network']
            sys_conf = self.settings['system']
            
            # Context actions
            options = {
                "1": f"Data Refresh Interval: [bold]{net['refresh_interval']}s[/bold]",
                "2": f"API Request Timeout: [bold]{net['timeout']}s[/bold]",
                "3": f"Max Cache Size: [bold]{sys_conf['cache_size_mb']} MB[/bold]",
                "0": "Back"
            }

            status = Table(box=box.SIMPLE, show_header=False)
            status.add_column("Field", style="bold cyan")
            status.add_column("Value", justify="right")
            status.add_row("Refresh Interval", f"{net['refresh_interval']}s")
            status.add_row("Timeout", f"{net['timeout']}s")
            status.add_row("Cache Size", f"{sys_conf['cache_size_mb']} MB")
            panel = Panel(status, title="⚡ SYSTEM & PERFORMANCE", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label="[>]",
                show_main=True,
                show_back=True,
                show_exit=True,
            )
            
            if choice == "0": break
            if choice == "m": break
            if choice == "x": Navigator.exit_app()
            if choice == "1":
                val = InputSafe.get_float("Enter seconds (10-3600):", 10, 3600)
                self.settings['network']['refresh_interval'] = int(val)
            if choice == "2":
                val = InputSafe.get_float("Enter seconds (1-60):", 1, 60)
                self.settings['network']['timeout'] = int(val)
            if choice == "3":
                val = InputSafe.get_float("Enter MB (1-1024):", 1, 1024)
                self.settings['system']['cache_size_mb'] = int(val)
            self._save_settings()

    # --- 4. Diagnostics ---
    def _run_deep_diagnostics(self):
        self.console.print("\n[bold]SYSTEM DIAGNOSTICS[/bold]")
        
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
            panel = self._build_info_panel()
            
            # Modular Menu Implementation
            options = {
                "1": "🔒 API & Security",
                "2": "🎨 Display & UX",
                "3": "⚡ System & Performance",
                "4": "🩺 Run Quick Diagnostics",
                "5": "💾 Reset Settings to Defaults",
                "0": "🔙 Return to Main"
            }
            
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label="[>]",
                show_main=True,
                show_back=True,
                show_exit=True,
            )

            from interfaces.menus import MainMenu as m # for cls/clear
            if choice == "0":
                m.clear_console()
                break
            if choice == "m":
                m.clear_console()
                break
            if choice == "x":
                Navigator.exit_app()
            elif choice == "1": self._menu_api_security()
            elif choice == "2": self._menu_display_ux()
            elif choice == "3": self._menu_system_perf()
            elif choice == "4": self._run_deep_diagnostics()
            elif choice == "5":
                if InputSafe.get_yes_no("Reset settings to defaults?"):
                    self.settings = self._default_settings()
                    self._save_settings()
