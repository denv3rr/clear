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
from rich.text import Text

from utils.input import InputSafe
from utils.system import SystemHost 
from utils.charts import ChartRenderer
from interfaces.shell import ShellRenderer
from interfaces.menu_layout import build_sidebar, build_status_header, compact_for_width
from interfaces.navigator import Navigator
from modules.client_store import DbClientStore
from modules.market_data.registry import build_feed_registry, summarize_feed_registry

class SettingsModule:
    def __init__(self):
        self.console = Console()

        self.settings_file = os.path.join(os.getcwd(), "config", "settings.json")
        self.settings = self._load_settings()
        stored_key = self.settings.get("credentials", {}).get("finnhub_key")
        if stored_key and not os.getenv("FINNHUB_API_KEY"):
            os.environ["FINNHUB_API_KEY"] = stored_key

    def _default_settings(self):
        return {
            "display": {
                "theme": "default",
                "color_highlight": "blue",
                "show_animations": True,
                "show_tips": False,
                "scroll_text": {
                    "prompt": {
                        "speed": 8.0,
                        "band_width": 6,
                        "trail": 0,
                        "highlight_style": "bold bright_white",
                        "base_style": "dim",
                    },
                    "warning": {
                        "speed": 8.0,
                        "band_width": 6,
                        "trail": 0,
                        "highlight_style": "bold bright_white",
                        "base_style": "dim",
                    },
                },
            },
            "network": {"refresh_interval": 60, "timeout": 5, "retries": 3},
            "system": {"cache_size_mb": 512, "log_level": "INFO"},
            "tools": {"perm_entropy_order": 3, "perm_entropy_delay": 1},
            "credentials": {"smtp": {}, "finnhub_key": ""},
            "intel": {"auto_fetch": True, "cache_ttl": 300, "news_cache_ttl": 600},
            "trackers": {
                "auto_refresh": True,
                "gui_auto_refresh": True,
                "gui_refresh_interval": 10,
                "include_commercial_flights": False,
                "include_private_flights": False,
            },
            "news": {
                "sources_enabled": ["CNBC Top", "CNBC World", "MarketWatch", "BBC Business"],
                "conflict_sources_enabled": ["CNBC World", "BBC Business", "MarketWatch"],
                "conflict_categories_enabled": ["conflict", "world", "defense", "shipping", "energy"],
                "aliases_file": "config/news_aliases.json",
            },
            "ai": {
                "enabled": True,
                "provider": "auto",
                "model_id": "rule_based_v1",
                "persona": "advisor_legal_v1",
                "cache_ttl": 21600,
                "cache_file": "data/ai_report_cache.json",
                "endpoint": "",
                "news_freshness_hours": 4,
            },
            "reporting": {
                "ai": {
                    "enabled": True,
                    "provider": "auto",
                    "model_id": "llama3",
                    "endpoint": "http://127.0.0.1:11434",
                    "timeout_seconds": 15,
                    "news_freshness_hours": 4,
                }
            },
        }

    def _load_settings(self):
        defaults = self._default_settings()
        if not os.path.exists(self.settings_file):
            return defaults
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return defaults
            # Shallow merge defaults
            for k, v in defaults.items():
                if k not in data or not isinstance(data.get(k), dict):
                    data[k] = v
            if "intel" not in data or not isinstance(data.get("intel"), dict):
                data["intel"] = defaults["intel"]
            if "tools" not in data or not isinstance(data.get("tools"), dict):
                data["tools"] = defaults["tools"]
            if "trackers" not in data or not isinstance(data.get("trackers"), dict):
                data["trackers"] = defaults["trackers"]
            if "news" not in data or not isinstance(data.get("news"), dict):
                data["news"] = defaults["news"]
            if "ai" not in data or not isinstance(data.get("ai"), dict):
                data["ai"] = defaults["ai"]
            if "display" not in data or not isinstance(data.get("display"), dict):
                data["display"] = defaults["display"]
            else:
                display = data["display"]
                if "scroll_text" not in display or not isinstance(display.get("scroll_text"), dict):
                    display["scroll_text"] = defaults["display"]["scroll_text"]
                else:
                    scroll_text = display["scroll_text"]
                    for preset, preset_defaults in defaults["display"]["scroll_text"].items():
                        if preset not in scroll_text or not isinstance(scroll_text.get(preset), dict):
                            scroll_text[preset] = preset_defaults
            return data
        except Exception:
            return defaults

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            self.console.print(f"[red]Error saving settings: {e}[/red]")

    # --- 1. API & Security ---
    def _menu_api_security(self):
        while True:
            compact = compact_for_width(self.console.width)
            # Context actions
            options = {
                "1": "Update Finnhub API Key",
                "2": "Update SMTP/Email Credentials",
                "3": "Clear All Stored Credentials",
                "4": "View Stored Credential Status",
                "0": "Back"
            }
            sidebar = build_sidebar(
                [("Security", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            
            status = Table(box=box.SIMPLE, show_header=False)
            status.add_column("Field", style="bold cyan")
            status.add_column("Value", justify="right")
            status.add_row("Finnhub Key", "SET" if os.getenv("FINNHUB_API_KEY") else "MISSING")
            status.add_row("SMTP Profile", "SET" if self.settings.get("credentials", {}).get("smtp") else "MISSING")
            panel = Panel(status, title="API & SECURITY SETTINGS", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
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
            tips = self.settings['display'].get('show_tips', False)
            scroll = self.settings['display'].get('scroll_text', {})
            prompt_speed = scroll.get('prompt', {}).get('speed', 14.0)
            compact = compact_for_width(self.console.width)
            
            # Context actions
            options = {
                "1": f"Highlight Color (Current: [bold {hl}]{hl}[/])",
                "2": f"UI Animations (Current: {anim})",
                "3": f"Show Tips (Current: {tips})",
                "4": f"Scroll Text (Prompt Speed: {prompt_speed})",
                "0": "Back"
            }
            sidebar = build_sidebar(
                [("Display", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            
            status = Table(box=box.SIMPLE, show_header=False)
            status.add_column("Field", style="bold cyan")
            status.add_column("Value", justify="right")
            status.add_row("Highlight Color", hl)
            status.add_row("Animations", str(anim))
            status.add_row("Show Tips", str(tips))
            status.add_row("Scroll Prompt Speed", str(prompt_speed))
            panel = Panel(status, title="DISPLAY & UX SETTINGS", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )
            
            if choice == "0": break
            if choice == "m": break
            if choice == "x": Navigator.exit_app()
            if choice == "1":
                c = InputSafe.get_string("Enter color (blue, green, magenta, gold1):")
                if c: self.settings['display']['color_highlight'] = c
            if choice == "2":
                self.settings['display']['show_animations'] = not self.settings['display']['show_animations']
            if choice == "3":
                self.settings['display']['show_tips'] = not bool(self.settings['display'].get('show_tips', False))
            if choice == "4":
                self._menu_scroll_text()
            self._save_settings()

    def _menu_scroll_text(self):
        while True:
            scroll = self.settings['display'].get('scroll_text', {})
            prompt = scroll.get("prompt", {})
            warning = scroll.get("warning", {})
            compact = compact_for_width(self.console.width)
            options = {
                "1": f"Edit Prompt Preset (Speed: {prompt.get('speed', 14.0)})",
                "2": f"Edit Warning Preset (Speed: {warning.get('speed', 14.0)})",
                "3": "Reset Scroll Presets to Defaults",
                "0": "Back",
            }
            sidebar = build_sidebar(
                [("Scroll Text", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            rows = Table(box=box.SIMPLE, show_header=False)
            rows.add_column("Preset", style="bold cyan")
            rows.add_column("Speed", justify="right")
            rows.add_column("Band", justify="right")
            rows.add_column("Trail", justify="right")
            rows.add_row(
                "Prompt",
                str(prompt.get("speed", 14.0)),
                str(prompt.get("band_width", 2)),
                str(prompt.get("trail", 0)),
            )
            rows.add_row(
                "Warning",
                str(warning.get("speed", 14.0)),
                str(warning.get("band_width", 2)),
                str(warning.get("trail", 0)),
            )
            panel = Panel(rows, title="SCROLL TEXT", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )
            if choice == "0" or choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()
            if choice == "1":
                self._menu_scroll_preset("prompt")
            if choice == "2":
                self._menu_scroll_preset("warning")
            if choice == "3":
                if InputSafe.get_yes_no("Reset scroll presets to defaults?"):
                    defaults = self._default_settings()
                    self.settings['display']['scroll_text'] = defaults['display']['scroll_text']
            self._save_settings()

    def _menu_scroll_preset(self, preset_name: str):
        while True:
            scroll = self.settings['display'].setdefault('scroll_text', {})
            preset = scroll.setdefault(preset_name, {})
            compact = compact_for_width(self.console.width)
            options = {
                "1": f"Speed (Current: {preset.get('speed', 14.0)})",
                "2": f"Band Width (Current: {preset.get('band_width', 2)})",
                "3": f"Trail (Current: {preset.get('trail', 0)})",
                "4": f"Highlight Style (Current: {preset.get('highlight_style', 'bold bright_white')})",
                "5": f"Base Style (Current: {preset.get('base_style', 'white')})",
                "0": "Back",
            }
            sidebar = build_sidebar(
                [(preset_name.title(), {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            rows = Table(box=box.SIMPLE, show_header=False)
            rows.add_column("Field", style="bold cyan")
            rows.add_column("Value", justify="right")
            rows.add_row("Speed", str(preset.get("speed", 14.0)))
            rows.add_row("Band Width", str(preset.get("band_width", 2)))
            rows.add_row("Trail", str(preset.get("trail", 0)))
            rows.add_row("Highlight Style", str(preset.get("highlight_style", "bold bright_white")))
            rows.add_row("Base Style", str(preset.get("base_style", "white")))
            panel = Panel(rows, title=f"{preset_name.upper()} SCROLL PRESET", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )
            if choice == "0" or choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()
            if choice == "1":
                val = InputSafe.get_float("Speed (0.1-60):", 0.1, 60)
                preset["speed"] = float(val)
            elif choice == "2":
                val = InputSafe.get_float("Band width (1-10):", 1, 10)
                preset["band_width"] = int(val)
            elif choice == "3":
                val = InputSafe.get_float("Trail (0-10):", 0, 10)
                preset["trail"] = int(val)
            elif choice == "4":
                val = InputSafe.get_string("Highlight style (e.g., bold bright_white):")
                if val:
                    preset["highlight_style"] = val
            elif choice == "5":
                val = InputSafe.get_string("Base style (e.g., white or dim):")
                if val:
                    preset["base_style"] = val
            scroll[preset_name] = preset
            self.settings['display']['scroll_text'] = scroll
            self._save_settings()

    # --- 3. System & Performance ---
    def _menu_system_perf(self):
        while True:
            net = self.settings['network']
            sys_conf = self.settings['system']
            intel = self.settings.get('intel', {})
            trackers = self.settings.get('trackers', {})
            compact = compact_for_width(self.console.width)
            
            # Context actions
            options = {
                "1": f"Data Refresh Interval: {net['refresh_interval']}s",
                "2": f"API Request Timeout: {net['timeout']}s",
                "3": f"Max Cache Size: {sys_conf['cache_size_mb']} MB",
                "4": f"Intel Auto Fetch: {intel.get('auto_fetch', True)}",
                "5": f"Intel Cache TTL: {intel.get('cache_ttl', 300)}s",
                "6": f"Trackers Auto Refresh: {trackers.get('auto_refresh', True)}",
                "7": f"GUI Auto Refresh: {trackers.get('gui_auto_refresh', True)}",
                "8": f"GUI Refresh Interval: {trackers.get('gui_refresh_interval', 10)}s",
                "9": f"News Cache TTL: {intel.get('news_cache_ttl', 600)}s",
                "0": "Back"
            }
            sidebar = build_sidebar(
                [("Performance", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )

            status = Table(box=box.SIMPLE, show_header=False)
            status.add_column("Field", style="bold cyan")
            status.add_column("Value", justify="right")
            status.add_row("Refresh Interval", f"{net['refresh_interval']}s")
            status.add_row("Timeout", f"{net['timeout']}s")
            status.add_row("Cache Size", f"{sys_conf['cache_size_mb']} MB")
            status.add_row("Intel Auto Fetch", str(intel.get("auto_fetch", True)))
            status.add_row("Intel Cache TTL", f"{intel.get('cache_ttl', 300)}s")
            status.add_row("Trackers Auto Refresh", str(trackers.get("auto_refresh", True)))
            status.add_row("GUI Auto Refresh", str(trackers.get("gui_auto_refresh", True)))
            status.add_row("GUI Refresh Interval", f"{trackers.get('gui_refresh_interval', 10)}s")
            status.add_row("News Cache TTL", f"{intel.get('news_cache_ttl', 600)}s")
            panel = Panel(status, title="SYSTEM & PERFORMANCE", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
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
            if choice == "4":
                self.settings['intel']['auto_fetch'] = not bool(self.settings['intel'].get('auto_fetch', True))
            if choice == "5":
                val = InputSafe.get_float("Enter seconds (60-900):", 60, 900)
                self.settings['intel']['cache_ttl'] = int(val)
            if choice == "6":
                self.settings['trackers']['auto_refresh'] = not bool(self.settings['trackers'].get('auto_refresh', True))
            if choice == "7":
                self.settings['trackers']['gui_auto_refresh'] = not bool(self.settings['trackers'].get('gui_auto_refresh', True))
            if choice == "8":
                val = InputSafe.get_float("Enter seconds (5-60):", 5, 60)
                self.settings['trackers']['gui_refresh_interval'] = int(val)
            if choice == "9":
                val = InputSafe.get_float("Enter seconds (120-1800):", 120, 1800)
                self.settings['intel']['news_cache_ttl'] = int(val)
            self._save_settings()

    def _menu_tools(self):
        while True:
            tools = self.settings.get("tools", {})
            order = tools.get("perm_entropy_order", 3)
            delay = tools.get("perm_entropy_delay", 1)
            dup_count, _ = self._duplicate_accounts_summary()
            compact = compact_for_width(self.console.width)

            options = {
                "1": f"Permutation Order (m) (Current: {order})",
                "2": f"Permutation Delay (tau) (Current: {delay})",
                "3": f"Remove Duplicate Accounts (Found: {dup_count})",
                "0": "Back",
            }
            sidebar = build_sidebar(
                [("Tools", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            rows = Table(box=box.SIMPLE, show_header=False)
            rows.add_column("Field", style="bold cyan", width=22)
            rows.add_column("Value", style="white", width=10, justify="right")
            rows.add_column("Notes", style="dim")
            rows.add_row("Permutation Order (m)", str(order), "Higher = more patterns; needs more data")
            rows.add_row("Permutation Delay (tau)", str(delay), "Spacing between points in the ordinal pattern")
            rows.add_row("Duplicate Accounts", str(dup_count), "Remove duplicate accounts")
            panel = Panel(rows, title="TOOLS SETTINGS", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )
            if choice == "0" or choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()
            if choice == "1":
                val = InputSafe.get_string("Permutation order (m, >=2):")
                if val and val.isdigit():
                    num = int(val)
                    if num >= 2:
                        tools["perm_entropy_order"] = num
                    else:
                        self.console.print("[yellow]Order must be >= 2.[/yellow]")
            elif choice == "2":
                val = InputSafe.get_string("Permutation delay (tau, >=1):")
                if val and val.isdigit():
                    num = int(val)
                    if num >= 1:
                        tools["perm_entropy_delay"] = num
                    else:
                        self.console.print("[yellow]Delay must be >= 1.[/yellow]")
            elif choice == "3":
                self._cleanup_duplicate_accounts()
            self.settings["tools"] = tools
            self._save_settings()

    def _menu_tracker_filters(self):
        while True:
            trackers = self.settings.get('trackers', {})
            compact = compact_for_width(self.console.width)
            options = {
                "1": f"Include Commercial Flights: [bold]{trackers.get('include_commercial_flights', False)}[/bold]",
                "2": f"Include Private Flights: [bold]{trackers.get('include_private_flights', False)}[/bold]",
                "0": "Back",
            }
            sidebar = build_sidebar(
                [("Filters", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            status = Table(box=box.SIMPLE, show_header=False)
            status.add_column("Field", style="bold cyan")
            status.add_column("Value", justify="right")
            status.add_row("Commercial Flights", str(trackers.get("include_commercial_flights", False)))
            status.add_row("Private Flights", str(trackers.get("include_private_flights", False)))
            note = Text(
                "Commercial/private traffic adds volume and can obscure high-signal events.",
                style="yellow",
            )
            panel = Panel(Group(note, status), title="TRACKER FILTERS", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )

            if choice == "0":
                break
            if choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()
            if choice == "1":
                self.settings['trackers']['include_commercial_flights'] = not bool(
                    self.settings['trackers'].get('include_commercial_flights', False)
                )
            if choice == "2":
                self.settings['trackers']['include_private_flights'] = not bool(
                    self.settings['trackers'].get('include_private_flights', False)
                )
            self._save_settings()

    def _menu_news_sources(self):
        from modules.market_data.collectors import DEFAULT_SOURCES, CONFLICT_CATEGORIES

        while True:
            news = self.settings.get("news", {})
            enabled = set([str(n).lower() for n in news.get("sources_enabled", [])])
            conflict_enabled = set([str(n).lower() for n in news.get("conflict_sources_enabled", [])])
            conflict_categories = set([str(n).lower() for n in news.get("conflict_categories_enabled", [])])
            compact = compact_for_width(self.console.width)

            options = {
                "0": "Back",
                "N": "Manage News Sources",
                "C": "Manage Conflict Sources",
                "K": "Manage Conflict Categories",
                "A": "Set Alias File",
            }
            rows = Table(box=box.SIMPLE, show_header=False)
            rows.add_column("Key", style="bold cyan", width=4)
            rows.add_column("Source", style="white")
            rows.add_column("Enabled", justify="right")

            rows.add_row("N", "News sources", f"{len(enabled)}/{len(DEFAULT_SOURCES)}")
            rows.add_row("C", "Conflict sources", f"{len(conflict_enabled)}/{len(DEFAULT_SOURCES)}")
            rows.add_row("K", "Conflict categories", f"{len(conflict_categories)}/{len(CONFLICT_CATEGORIES)}")
            rows.add_row("A", "Alias file", str(news.get("aliases_file", "config/news_aliases.json")))

            sidebar = build_sidebar(
                [("Sources", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )

            note = Text(
                "Configure default RSS sources and conflict filters.",
                style="dim",
            )
            panel = Panel(Group(note, rows), title="NEWS SOURCES", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )

            if choice == "0":
                break
            if choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()

            if choice == "N":
                self._menu_news_source_picker(
                    "News Sources",
                    DEFAULT_SOURCES,
                    enabled,
                    "sources_enabled",
                )
            elif choice == "C":
                self._menu_news_source_picker(
                    "Conflict Sources",
                    DEFAULT_SOURCES,
                    conflict_enabled,
                    "conflict_sources_enabled",
                )
            elif choice == "K":
                self._menu_conflict_categories(CONFLICT_CATEGORIES, conflict_categories)
            elif choice == "A":
                val = InputSafe.get_string("Alias file path (blank for default):")
                news = self.settings.get("news", {})
                if val.strip():
                    alias_path = val.strip()
                    if not os.path.exists(alias_path):
                        proceed = InputSafe.get_yes_no("Alias file not found. Save anyway?")
                        if not proceed:
                            continue
                    else:
                        from modules.market_data.intel import validate_alias_file
                        ok, message = validate_alias_file(alias_path)
                        if not ok:
                            proceed = InputSafe.get_yes_no(f"Alias file invalid ({message}). Save anyway?")
                            if not proceed:
                                continue
                    news["aliases_file"] = alias_path
                else:
                    news["aliases_file"] = "config/news_aliases.json"
                self.settings["news"] = news
                self._save_settings()

    def _menu_news_source_picker(self, title: str, sources: list, enabled: set, target_key: str):
        while True:
            options = {"0": "Back"}
            rows = Table(box=box.SIMPLE, show_header=False)
            rows.add_column("Key", style="bold cyan", width=4)
            rows.add_column("Source", style="white")
            rows.add_column("Enabled", justify="right")

            for idx, src in enumerate(sources, 1):
                key = str(idx)
                is_on = src.name.lower() in enabled
                options[key] = f"Toggle {src.name}"
                rows.add_row(key, src.name, "YES" if is_on else "NO")

            compact = compact_for_width(self.console.width)
            sidebar = build_sidebar(
                [("Sources", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            panel = Panel(rows, title=title, box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )

            if choice == "0" or choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(sources):
                    name = sources[idx].name
                    key = name.lower()
                    if key in enabled:
                        enabled.remove(key)
                    else:
                        enabled.add(key)
                    news = self.settings.get("news", {})
                    news[target_key] = [s.name for s in sources if s.name.lower() in enabled]
                    self.settings["news"] = news
                    self._save_settings()

    def _menu_conflict_categories(self, categories: list, enabled: set):
        while True:
            options = {"0": "Back"}
            rows = Table(box=box.SIMPLE, show_header=False)
            rows.add_column("Key", style="bold cyan", width=4)
            rows.add_column("Category", style="white")
            rows.add_column("Enabled", justify="right")

            for idx, name in enumerate(categories, 1):
                key = str(idx)
                is_on = name.lower() in enabled
                options[key] = f"Toggle {name}"
                rows.add_row(key, name, "YES" if is_on else "NO")

            compact = compact_for_width(self.console.width)
            sidebar = build_sidebar(
                [("Categories", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            panel = Panel(rows, title="Conflict Categories", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )

            if choice == "0" or choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(categories):
                    name = str(categories[idx]).lower()
                    if name in enabled:
                        enabled.remove(name)
                    else:
                        enabled.add(name)
                    news = self.settings.get("news", {})
                    news["conflict_categories_enabled"] = [c for c in categories if c.lower() in enabled]
                    self.settings["news"] = news
                    self._save_settings()

    def _menu_ai_synthesis(self):
        while True:
            ai = self.settings.get("ai", {})
            provider = ai.get("provider", "auto")
            persona = ai.get("persona", "advisor_legal_v1")
            cache_ttl = ai.get("cache_ttl", 21600)
            model_id = ai.get("model_id", "rule_based_v1")
            endpoint = ai.get("endpoint", "")
            enabled = ai.get("enabled", True)
            freshness = ai.get("news_freshness_hours", 4)
            compact = compact_for_width(self.console.width)

            options = {
                "1": f"Enabled (Current: {enabled})",
                "2": f"Provider (Current: {provider})",
                "3": f"Model ID (Current: {model_id})",
                "4": f"Persona (Current: {persona})",
                "5": f"Cache TTL (Current: {cache_ttl}s)",
                "6": f"Endpoint (Current: {endpoint or 'none'})",
                "7": f"News Freshness (Current: {freshness}h)",
                "0": "Back",
            }
            sidebar = build_sidebar(
                [("AI", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            rows = Table(box=box.SIMPLE, show_header=False)
            rows.add_column("Field", style="bold cyan", width=16)
            rows.add_column("Value", style="white")
            rows.add_row("Enabled", str(enabled))
            rows.add_row("Provider", str(provider))
            rows.add_row("Model ID", str(model_id))
            rows.add_row("Persona", str(persona))
            rows.add_row("Cache TTL", f"{cache_ttl}s")
            rows.add_row("Endpoint", endpoint or "none")
            rows.add_row("News Freshness", f"{freshness}h")
            panel = Panel(rows, title="AI SYNTHESIS", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )
            if choice == "0" or choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()
            if choice == "1":
                ai["enabled"] = not bool(ai.get("enabled", True))
            elif choice == "2":
                val = InputSafe.get_string("Provider (auto, ollama, local_http, rule_based):")
                if val:
                    ai["provider"] = val.strip()
            elif choice == "3":
                val = InputSafe.get_string("Model ID:")
                if val:
                    ai["model_id"] = val.strip()
            elif choice == "4":
                val = InputSafe.get_string("Persona:")
                if val:
                    ai["persona"] = val.strip()
            elif choice == "5":
                val = InputSafe.get_string("Cache TTL (seconds):")
                if val and val.isdigit():
                    ai["cache_ttl"] = int(val)
            elif choice == "6":
                val = InputSafe.get_string("Endpoint URL (blank to clear):")
                ai["endpoint"] = val.strip()
            elif choice == "7":
                val = InputSafe.get_string("News freshness (hours):")
                if val and val.isdigit():
                    ai["news_freshness_hours"] = int(val)
            self.settings["ai"] = ai
            self._save_settings()

    def _menu_reporting_ai(self):
        while True:
            reporting = self.settings.get("reporting", {})
            ai = reporting.get("ai", {})
            provider = ai.get("provider", "auto")
            model_id = ai.get("model_id", "llama3")
            endpoint = ai.get("endpoint", "http://127.0.0.1:11434")
            enabled = ai.get("enabled", True)
            timeout = ai.get("timeout_seconds", 15)
            freshness = ai.get("news_freshness_hours", 4)
            compact = compact_for_width(self.console.width)

            options = {
                "1": f"Enabled (Current: {enabled})",
                "2": f"Provider (Current: {provider})",
                "3": f"Model ID (Current: {model_id})",
                "4": f"Endpoint (Current: {endpoint or 'none'})",
                "5": f"Timeout (Current: {timeout}s)",
                "6": f"News Freshness (Current: {freshness}h)",
                "R": "Refresh Health",
                "0": "Back",
            }
            sidebar = build_sidebar(
                [("Reporting AI", {k: v for k, v in options.items() if k != "0"})],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            rows = Table(box=box.SIMPLE, show_header=False)
            rows.add_column("Field", style="bold cyan", width=16)
            rows.add_column("Value", style="white")
            from modules.reporting.engine import report_health_check
            health = report_health_check()
            rows.add_row("Enabled", str(enabled))
            rows.add_row("Provider", str(provider))
            rows.add_row("Model ID", str(model_id))
            rows.add_row("Endpoint", endpoint or "none")
            rows.add_row("Timeout", f"{timeout}s")
            rows.add_row("News Freshness", f"{freshness}h")
            rows.add_row("Ollama", "OK" if health.get("ollama_reachable") else "Unavailable")
            rows.add_row("Local HTTP", "OK" if health.get("local_http_reachable") else "Unavailable")
            panel = Panel(rows, title="REPORTING AI", box=box.ROUNDED)
            choice = ShellRenderer.render_and_prompt(
                Group(panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )
            if choice == "0" or choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()
            if choice == "R":
                continue
            if choice == "1":
                ai["enabled"] = not bool(ai.get("enabled", True))
            elif choice == "2":
                val = InputSafe.get_string("Provider (auto, ollama, local_http, rule_based):")
                if val:
                    ai["provider"] = val.strip()
            elif choice == "3":
                val = InputSafe.get_string("Model ID:")
                if val:
                    ai["model_id"] = val.strip()
            elif choice == "4":
                val = InputSafe.get_string("Endpoint URL (blank to clear):")
                ai["endpoint"] = val.strip()
            elif choice == "5":
                val = InputSafe.get_string("Timeout (seconds):")
                if val and val.isdigit():
                    ai["timeout_seconds"] = int(val)
            elif choice == "6":
                val = InputSafe.get_string("News freshness (hours):")
                if val and val.isdigit():
                    ai["news_freshness_hours"] = int(val)
            reporting["ai"] = ai
            self.settings["reporting"] = reporting
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

        feed_registry = build_feed_registry()
        feed_summary = summarize_feed_registry(feed_registry)
        health_counts = feed_summary.get("health_counts", {})
        health_line = (
            f"ok {health_counts.get('ok', 0)} | "
            f"degraded {health_counts.get('degraded', 0)} | "
            f"backoff {health_counts.get('backoff', 0)} | "
            f"unknown {health_counts.get('unknown', 0)}"
        )

        feed_summary_table = Table(box=box.SIMPLE, show_header=False)
        feed_summary_table.add_column("Metric", style="dim", width=16)
        feed_summary_table.add_column("Value", style="white")
        feed_summary_table.add_row(
            "Sources",
            f"{feed_summary.get('configured', 0)}/{feed_summary.get('total', 0)}",
        )
        feed_summary_table.add_row("Unconfigured", str(feed_summary.get("unconfigured", 0)))
        feed_summary_table.add_row("Health", health_line)

        category_panel = None
        categories = feed_summary.get("categories", {}) or {}
        if categories:
            category_table = Table(box=box.SIMPLE, show_header=True)
            category_table.add_column("Category", style="bold cyan")
            category_table.add_column("Configured", justify="right")
            category_table.add_column("Total", justify="right")
            for name in sorted(categories.keys()):
                stats = categories.get(name, {})
                category_table.add_row(
                    name.title(),
                    str(stats.get("configured", 0)),
                    str(stats.get("total", 0)),
                )
            category_panel = Panel(
                category_table,
                title="Feed Categories",
                border_style="cyan",
                box=box.SIMPLE,
            )

        warnings_panel = None
        warnings = feed_summary.get("warnings") or []
        if warnings:
            warning_text = "\n".join(f"- {warning}" for warning in warnings)
            warnings_panel = Panel(
                Text(warning_text, style="yellow"),
                title="Feed Warnings",
                border_style="yellow",
                box=box.SIMPLE,
            )

        panels = [
            table,
            Panel(feed_summary_table, title="Feed Registry", border_style="cyan", box=box.SIMPLE),
        ]
        if category_panel:
            panels.append(category_panel)
        if warnings_panel:
            panels.append(warnings_panel)
        self.console.print(Group(*panels))
        InputSafe.pause()

    def _duplicate_accounts_summary(self):
        try:
            summary = DbClientStore().find_duplicate_accounts()
            return (
                int(summary.get('count', 0) or 0),
                int(summary.get('clients', 0) or 0),
            )
        except Exception:
            return 0, 0

    def _cleanup_duplicate_accounts(self):
        count, clients = self._duplicate_accounts_summary()
        if count <= 0:
            self.console.print('[dim]No duplicate accounts detected.[/dim]')
            InputSafe.pause()
            return
        if not InputSafe.get_yes_no(
            f'Remove {count} duplicate account(s) across {clients} client(s)?'
        ):
            return
        result = DbClientStore().remove_duplicate_accounts()
        removed = int(result.get('removed', 0) or 0)
        self.console.print(f'[green]Removed {removed} duplicate account(s).[/green]')
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

        dup_count, dup_clients = self._duplicate_accounts_summary()
        dup_label = f"{dup_count} ({dup_clients} clients)" if dup_count else "0"
        dup_style = "bold red" if dup_count else "dim"
        left_table.add_row("DUP ACCTS:", f"[{dup_style}]{dup_label}[/{dup_style}]")

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
            compact = compact_for_width(self.console.width)
            dup_count, dup_clients = self._duplicate_accounts_summary()
            panel = self._build_info_panel()

            # Modular Menu Implementation
            options = {
                "1": "API & Security",
                "2": "Display & UX",
                "3": "System & Performance",
                "4": "Tracker Filters",
                "5": "News Sources",
                "6": "AI Synthesis",
                "7": "Reporting AI",
                "8": "Tools",
                "9": "Run Quick Diagnostics",
                "10": "Reset Settings to Defaults",
                "11": "Normalize Lot Timestamps",
                "0": "Return to Main",
            }
            sidebar = build_sidebar(
                [
                    ("Settings", {
                        "1": "API & Security",
                        "2": "Display & UX",
                        "3": "System & Performance",
                        "4": "Tracker Filters",
                        "5": "News Sources",
                        "6": "AI Synthesis",
                        "7": "Reporting AI",
                        "8": "Tools",
                    }),
                    ("Diagnostics", {
                        "9": "Run Quick Diagnostics",
                        "10": "Reset to Defaults",
                        "11": "Normalize Lot Timestamps",
                    }),
                ],
                show_main=True,
                show_back=True,
                show_exit=True,
                compact=compact,
            )
            status_panel = build_status_header(
                "Status",
                [
                    ("Auto Fetch", str(self.settings.get("intel", {}).get("auto_fetch", True))),
                    ("Intel TTL", f"{self.settings.get('intel', {}).get('cache_ttl', 300)}s"),
                    ("News TTL", f"{self.settings.get('intel', {}).get('news_cache_ttl', 600)}s"),
                    ("Trackers", str(self.settings.get("trackers", {}).get("auto_refresh", True))),
                    ("AI", str(self.settings.get("ai", {}).get("enabled", True))),
                    ("Report AI", str(self.settings.get("reporting", {}).get("ai", {}).get("enabled", True))),
                    ("Dup Accts", f"{dup_count}"),
                ],
                compact=compact,
            )

            choice = ShellRenderer.render_and_prompt(
                Group(status_panel, panel),
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                sidebar_override=sidebar,
            )

            from interfaces.menus import MainMenu as m  # for cls/clear
            if choice == "0":
                m.clear_console()
                break
            if choice == "m":
                m.clear_console()
                break
            if choice == "x":
                Navigator.exit_app()
            elif choice == "1":
                self._menu_api_security()
            elif choice == "2":
                self._menu_display_ux()
            elif choice == "3":
                self._menu_system_perf()
            elif choice == "4":
                self._menu_tracker_filters()
            elif choice == "5":
                self._menu_news_sources()
            elif choice == "6":
                self._menu_ai_synthesis()
            elif choice == "7":
                self._menu_reporting_ai()
            elif choice == "8":
                self._menu_tools()
            elif choice == "9":
                self._run_deep_diagnostics()
            elif choice == "10":
                if InputSafe.get_yes_no("Reset settings to defaults?"):
                    self.settings = self._default_settings()
                    self._save_settings()
            elif choice == "11":
                self._normalize_legacy_lot_timestamps()

    def _normalize_legacy_lot_timestamps(self):
        self.console.print("\n[bold]Normalize Lot Timestamps[/bold]")
        if not InputSafe.get_yes_no("Rewrite legacy lot timestamps to ISO-8601?"):
            return
        try:
            from modules.client_mgr.data_handler import DataHandler
            path = DataHandler.CLIENT_FILE
            if not os.path.exists(path):
                self.console.print("[yellow]No clients.json found.[/yellow]")
                return
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            payload, migrated = DataHandler._migrate_clients_payload(payload)
            if not migrated:
                self.console.print("[dim]No legacy timestamps found.[/dim]")
                return
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
            self.console.print("[green]Lot timestamps normalized to ISO-8601.[/green]")
        except Exception as exc:
            self.console.print(f"[red]Failed to normalize lot timestamps: {exc}[/red]")
