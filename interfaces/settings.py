import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box
import os

from utils.input import InputSafe
from utils.text_fx import TextEffectManager
from utils.system import SystemHost 

class SettingsModule:
    def __init__(self):
        self.console = Console()
        self.text_fx = TextEffectManager()
        # Simple storage for settings (can be replaced by a config file handler later)
        self.settings = {
            "display_color": "blue",
            "refresh_interval": 60 
        }

    # --- New Placeholder Implementation Methods ---

    def _update_api_key(self):
        """
        Implements option [1] - Update Finnhub API Key.
        Writes the key to the root /.env file and updates os.environ.
        """
        self.console.clear()
        self.console.print("\n[bold]🔑 API KEY MANAGEMENT[/bold]")
        self.console.print("--- Finnhub Key Update ---")
        
        # 1. Get new key from user
        new_key = InputSafe.get_string("Enter new FINNHUB_API_KEY (or leave blank to cancel)")
        
        if not new_key:
            self.console.print("[yellow]API Key update cancelled.[/yellow]")
            InputSafe.pause()
            return
            
        env_file_path = os.path.join(os.getcwd(), ".env")
        key_macro = "FINNHUB_API_KEY"
        
        try:
            lines = []
            key_found = False
            
            # 2. Read existing content (if file exists)
            if os.path.exists(env_file_path):
                with open(env_file_path, 'r') as f:
                    lines = f.readlines()
                
                # 3. Find and replace the key in memory
                for i, line in enumerate(lines):
                    if line.strip().startswith(f"{key_macro}="):
                        lines[i] = f"{key_macro}={new_key}\n"
                        key_found = True
                        break
            
            # 4. If key not found, append it to the lines
            if not key_found:
                # Ensure a newline if appending to a non-empty file
                if lines and not lines[-1].endswith('\n'):
                    lines.append('\n')
                lines.append(f"{key_macro}={new_key}\n")

            # 5. Write the updated content back to the .env file
            with open(env_file_path, 'w') as f:
                f.writelines(lines)
                
            # 6. Update the environment variable for the current session immediately
            os.environ[key_macro] = new_key
            
            self.console.print(f"[green]SUCCESS:[/green] Key saved to {env_file_path} and activated for current session.")
            self.console.print(f"[dim]Key value: {new_key[:4]}...[/dim]")

        except Exception as e:
            self.console.print(f"[red]ERROR:[/red] Could not update .env file.")
            self.console.print(f"[dim]Please ensure file permissions are correct. Details: {e}[/dim]")
            
        InputSafe.pause()

    def _manage_credentials(self):
        """Implements option [2] - Manage Other Credentials."""
        self.console.clear()
        self.console.print("\n[bold]📄 OTHER CREDENTIALS[/bold]")
        self.console.print("Here you would manage non-API keys, such as email credentials or database secrets.")
        self.console.print("[dim]Feature under construction...[/dim]")
        InputSafe.pause()

    def _change_display_preferences(self):
        """Implements option [3] - Change Display Preferences."""
        self.console.clear()
        self.console.print("\n[bold]📝 DISPLAY PREFERENCES[/bold]")
        self.console.print(f"Current Highlight Color: [bold {self.settings['display_color']}]{self.settings['display_color'].upper()}[/bold {self.settings['display_color']}]")
        new_color = InputSafe.get_string("Enter new highlight color (e.g., 'red', 'green', 'blue', or cancel):")
        if new_color and new_color.lower() not in ['cancel', 'c', '0']:
            self.settings['display_color'] = new_color.lower()
            self.console.print(f"[green]Display color updated to [bold {new_color.lower()}]{new_color.upper()}[/bold {new_color.lower()}].[/green]")
        else:
            self.console.print("[yellow]Display preferences update cancelled.[/yellow]")
        InputSafe.pause()

    def _configure_refresh_intervals(self):
        """Implements option [4] - Configure Data Refresh Intervals."""
        self.console.clear()
        self.console.print("\n[bold]⏱️ REFRESH INTERVALS[/bold]")
        self.console.print(f"Current data refresh interval: [bold]{self.settings['refresh_interval']} seconds[/bold].")
        
        new_interval_str = InputSafe.get_string("Enter new interval in seconds (e.g., 30, 90, or cancel):")
        
        if new_interval_str and new_interval_str.isdigit():
            new_interval = int(new_interval_str)
            self.settings['refresh_interval'] = new_interval
            self.console.print(f"[green]Refresh interval updated to {new_interval} seconds.[/green]")
        else:
            self.console.print("[yellow]Refresh interval update cancelled or invalid input.[/yellow]")
        InputSafe.pause()


    def _run_diagnostics(self):
        """Implements option [5] - Run System Diagnostics/Health Check."""
        self.console.clear()
        self.console.print("\n[bold]🛠️ SYSTEM DIAGNOSTICS[/bold]")
        self.console.print("Running basic health checks...")
        
        # Re-fetch info to show live data
        data = SystemHost.get_info()
        self.console.print(f"* CPU Status: [bold]{data['cpu_usage']}[/bold]")
        self.console.print(f"* Memory Status: [bold]{data['mem_usage']}[/bold]")
        
        finnhub_status = "OK" if data["finnhub_status"] else "FAILURE (Key Missing)"
        finnhub_color = "green" if data["finnhub_status"] else "red"
        self.console.print(f"* Finnhub API Key Check: [{finnhub_color}]{finnhub_status}[/{finnhub_color}]")
        self.console.print("[green]Diagnostics complete.[/green]")
        InputSafe.pause()

    # --- Info Panel Helper (kept the same) ---
    def _build_info_panel(self) -> Panel:
        """Helper to build and return the main status info panel with detailed system info."""
        # ... (Method contents remain the same as the previous correct version)
        try:
            # Get the new, detailed system data
            data = SystemHost.get_info()
        except Exception:
            # Fallback for when system info retrieval (psutil) fails
            data = {
                "hostname": "Unknown", "user": "User", "os": "Unknown", 
                "ip": "0.0.0.0", "login_time": "Now", "finnhub_status": False,
                "cpu_usage": "N/A", "mem_usage": "N/A", "python_version": "N/A"
            }

        # --- Setup the Grid ---
        # Grid structured to hold two main columns of info
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", width=25)
        grid.add_column(justify="left")

        # --- System Identity (Left Column) ---
        grid.add_row(f"[bold white]IDENTITY:[/bold white]", "")
        grid.add_row(f"[bold cyan]  HOSTNAME:[/bold cyan]", f"{data['hostname']}")
        grid.add_row(f"[bold cyan]  USER:[/bold cyan]", f"{data['user']}")
        grid.add_row(f"[bold cyan]  OS/PLATFORM:[/bold cyan]", f"{data['os']}")
        grid.add_row("")

        # --- Network (Left Column) ---
        grid.add_row(f"[bold white]NETWORK:[/bold white]", "")
        grid.add_row(f"[bold cyan]  LOCAL IP:[/bold cyan]", f"{data['ip']}")
        grid.add_row("")

        # --- System Resources (Right Column) ---
        grid.add_row(f"[bold white]RESOURCES:[/bold white]", "")
        grid.add_row(f"[bold magenta]  PYTHON VER:[/bold magenta]", f"{data['python_version']}")
        grid.add_row(f"[bold magenta]  CPU USAGE:[/bold magenta]", f"{data['cpu_usage']}")
        grid.add_row(f"[bold magenta]  MEM USAGE:[/bold magenta]", f"{data['mem_usage']}")
        grid.add_row("")
        
        # --- API/Status (Right Column) ---
        color = "green" if data["finnhub_status"] else "red"
        status = "ACTIVE" if data["finnhub_status"] else "MISSING"

        grid.add_row(f"[bold white]STATUS & TIME:[/bold white]", "")
        grid.add_row(f"[bold yellow]  SYSTEM TIME:[/bold yellow]", f"{data['login_time']}")
        grid.add_row(f"[bold yellow]  FINNHUB KEY:[/bold yellow]", f"[{color}]{status}[/{color}]")

        # --- Final Panel Construction ---
        info_panel = Panel(
            Align.center(grid, vertical="middle"),
            box=box.DOUBLE,
            border_style="blue",
            title="[bold blue]SYSTEM HEALTH & API STATUS[/bold blue]",
            padding=(1, 4)
        )
        return info_panel


    # --- Main Run Loop (calls updated methods) ---
    def run(self):
        """Main loop for the settings module."""
        while True:
            self.console.clear()
            
            # 1. Build and Display the detailed info panel
            info_panel = self._build_info_panel()
            self.console.print(info_panel)

            # 2. Display Detailed Settings Options
            self.console.print("\n[bold gold1]CONFIGURATION MENU:[/bold gold1]")
            self.console.print("--- API & Credentials ---")
            self.console.print("[1] 🔑 Update Finnhub API Key")
            self.console.print("[2] 📄 Manage Other Credentials (e.g., Email)")
            self.console.print("--- Application Behavior ---")
            self.console.print("[3] 📝 Change Display Preferences (Colors, Font)")
            self.console.print("[4] ⏱️ Configure Data Refresh Intervals")
            self.console.print("--- System & Diagnostics ---")
            self.console.print("[5] 🛠️ Run System Diagnostics/Health Check")
            self.console.print("[0] 🔙 Return to Main Menu")
            
            choice = InputSafe.get_option(["1", "2", "3", "4", "5", "0"], prompt_text="[>]")
            
            if choice == "0":
                self.console.clear()
                break
            elif choice == "1":
                self._update_api_key()
            elif choice == "2":
                self._manage_credentials()
            elif choice == "3":
                self._change_display_preferences()
            elif choice == "4":
                self._configure_refresh_intervals()
            elif choice == "5":
                self._run_diagnostics()