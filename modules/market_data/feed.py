import time

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box
from rich.text import Text

from utils.input import InputSafe
from interfaces.navigator import Navigator
from modules.market_data.finnhub_client import FinnhubWrapper
from modules.market_data.yfinance_client import YahooWrapper
from modules.market_data.trackers import GlobalTrackers
from utils.clear_access import ClearAccessManager
from utils.charts import ChartRenderer
from interfaces.shell import ShellRenderer
from utils.scroll_text import build_scrolling_line

class MarketFeed:
    def __init__(self):
        self.console = Console()
        self.finnhub = FinnhubWrapper()
        self.yahoo = YahooWrapper()
        self.trackers = GlobalTrackers()
        self.clear_access = ClearAccessManager()
        
        # Default View State
        self.current_period = "1d"
        self.current_interval = "15m"
        
        # Preset Intervals
        # Format: (Display Label, API Period, API Interval)
        self.interval_options = [
            ("1D", "1d", "15m"),   
            ("5D", "5d", "60m"),
            ("1M", "1mo", "1d"),
            ("3M", "3mo", "1d"),
            ("1Y", "1y", "1wk")
        ]
        self.interval_idx = 0

    def toggle_interval(self):
        """Cycles to the next interval option."""
        self.interval_idx = (self.interval_idx + 1) % len(self.interval_options)
        label, p, i = self.interval_options[self.interval_idx]
        self.current_period = p
        self.current_interval = i
        return label

    def run(self):
        """Standard interaction loop for the Market Module."""
        while True:
            # Display current settings in the view
            current_label = self.interval_options[self.interval_idx][0]
            
            panel = self.display_futures(view_label=current_label)
            options = {
                "1": "Ticker Search",
                "2": "Force Refresh",
                "3": f"Change Interval ({current_label})",
                "4": "Global Trackers",
                "0": "Return to Main Menu",
            }
            ShellRenderer.render(
                Group(panel),
                context_actions=options,
                show_main=True,
                show_back=True,
                show_exit=True,
                show_header=False,
            )
            choice = InputSafe.get_option(list(options.keys()) + ["m", "x"], prompt_text="[>]").lower()
            
            if choice == "0" or choice == "m":
                break
            elif choice == "x":
                Navigator.exit_app()
            elif choice == "1":
                self.stock_lookup_loop()
            elif choice == "2":
                # Clear fast cache to force real refresh
                self.yahoo._FAST_CACHE.clear()
                continue 
            elif choice == "3":
                new_label = self.toggle_interval()
            elif choice == "4":
                self.run_global_trackers()

    def run_global_trackers(self):
        mode = "combined"
        cadence_options = [5, 10, 15, 30]
        cadence_idx = 1
        paused = False
        last_refresh = 0.0
        snapshot = self.trackers.get_snapshot(mode=mode)
        category_filter = "all"

        try:
            import msvcrt
            use_live = True
        except Exception:
            use_live = False

        if not use_live:
            panel = self.trackers.render(mode=mode, snapshot=snapshot)
            options = {
                "1": "Flights",
                "2": "Shipping",
                "3": "Combined",
                "4": "Refresh",
                "0": "Back",
            }
            ShellRenderer.render(
                Group(panel),
                context_actions=options,
                show_main=True,
                show_back=True,
                show_exit=True,
                show_header=False,
            )
            choice = InputSafe.get_option(list(options.keys()) + ["m", "x"], prompt_text="[>]").lower()
            if choice in ("0", "m"):
                return
            if choice == "x":
                Navigator.exit_app()
            return

        from rich.live import Live
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        from rich import box

        options = {
            "1": "Flights",
            "2": "Shipping",
            "3": "Combined",
            "4": "Refresh",
            "5": "Clear Access",
            "C": "Cadence",
            "F": "Category Filter",
            "A": "Filter: All",
            "SPC": "Pause/Resume",
            "0": "Back",
        }

        def _available_categories(data: dict) -> list[str]:
            categories = sorted({str(pt.get("category", "")).lower() for pt in data.get("points", []) if pt.get("category")})
            return ["all"] + categories if categories else ["all"]

        def build_layout():
            filtered = GlobalTrackers.apply_category_filter(snapshot, category_filter)
            max_rows = max(8, self.console.height - 18)
            panel = self.trackers.render(
                mode=mode,
                snapshot=filtered,
                filter_label=category_filter,
                max_rows=max_rows,
            )
            access_label = "Active" if self.clear_access.has_access() else "Inactive"
            options["5"] = f"Clear Access ({access_label})"
            sidebar = ShellRenderer._build_sidebar(
                {k: v for k, v in options.items() if k in ("1", "2", "3", "4", "5", "C", "F", "A", "SPC", "0")},
                show_main=True,
                show_back=True,
                show_exit=True,
            )
            status = "PAUSED" if paused else "LIVE"
            cadence = cadence_options[cadence_idx]
            footer = Text.assemble(
                ("[>]", "dim"),
                (" ", "dim"),
                (status, "bold green" if status == "LIVE" else "bold yellow"),
                (" | Cadence: ", "dim"),
                (f"{cadence}s", "bold cyan"),
                (" | 1/2/3 mode 4 refresh 5 access C cadence F filter A all Space pause 0 back M main X exit", "dim"),
            )
            mode_hint = Text.assemble(
                ("Mode: ", "dim"),
                ("1", "bold bright_white"),
                (" Flights  ", "cyan"),
                ("2", "bold bright_white"),
                (" Shipping  ", "cyan"),
                ("3", "bold bright_white"),
                (" Combined", "cyan"),
            )
            footer_panel = Panel(Group(footer, mode_hint), box=box.SQUARE, border_style="dim")

            layout = Table.grid(expand=True)
            layout.add_column(ratio=1)
            body = Table.grid(expand=True)
            body.add_column(width=30)
            body.add_column(ratio=1)
            body.add_row(sidebar, Group(panel))
            layout.add_row(body)
            layout.add_row(footer_panel)
            return layout

        dirty = True
        with Live(build_layout(), console=self.console, refresh_per_second=1, screen=True) as live:
            while True:
                now = time.time()
                cadence = cadence_options[cadence_idx]
                if not paused and (now - last_refresh) >= cadence:
                    self.trackers.refresh(force=True)
                    snapshot = self.trackers.get_snapshot(mode=mode)
                    last_refresh = now
                    dirty = True

                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\r", "\n"):
                        pass
                    elif ch == " ":
                        paused = not paused
                        dirty = True
                    else:
                        key = ch.lower()
                        if key == "0":
                            return
                        if key == "m":
                            return
                        if key == "x":
                            Navigator.exit_app()
                        if key == "1":
                            mode = "flights"
                            snapshot = self.trackers.get_snapshot(mode=mode)
                            category_filter = "all"
                            dirty = True
                        elif key == "2":
                            mode = "ships"
                            snapshot = self.trackers.get_snapshot(mode=mode)
                            category_filter = "all"
                            dirty = True
                        elif key == "3":
                            mode = "combined"
                            snapshot = self.trackers.get_snapshot(mode=mode)
                            category_filter = "all"
                            dirty = True
                        elif key == "4":
                            self.trackers.refresh(force=True)
                            snapshot = self.trackers.get_snapshot(mode=mode)
                            last_refresh = time.time()
                            dirty = True
                        elif key == "5":
                            self._clear_access_flow()
                            dirty = True
                        elif key == "c":
                            cadence_idx = (cadence_idx + 1) % len(cadence_options)
                            dirty = True
                        elif key == "f":
                            categories = _available_categories(snapshot)
                            if category_filter not in categories:
                                category_filter = "all"
                            idx = categories.index(category_filter)
                            category_filter = categories[(idx + 1) % len(categories)]
                            dirty = True
                        elif key == "a":
                            category_filter = "all"
                            dirty = True
                if dirty:
                    live.update(build_layout(), refresh=True)
                    dirty = False
                time.sleep(0.1)

    def _clear_access_flow(self):
        from rich.panel import Panel
        from rich.text import Text
        from rich import box
        import webbrowser

        status = "Active" if self.clear_access.has_access() else "Inactive"
        info = Text()
        info.append("Clear Access\n", style="bold")
        info.append(f"Status: {status}\n\n", style="dim")
        info.append("Purchase Link:\n", style="bold cyan")
        info.append(f"{self.clear_access.PRODUCT_URL}\n\n", style="white")
        info.append("After purchase, paste your access code below.\n", style="dim")

        panel = Panel(info, title="Clear Access", box=box.ROUNDED, border_style="cyan")
        ShellRenderer.render(
            Group(panel),
            context_actions={"1": "Open Purchase Link", "2": "Enter Access Code", "3": "Clear Code", "0": "Back"},
            show_main=True,
            show_back=True,
            show_exit=True,
            show_header=False,
        )
        choice = InputSafe.get_option(["1", "2", "3", "0", "m", "x"], prompt_text="[>]").lower()
        if choice in ("0", "m"):
            return
        if choice == "x":
            Navigator.exit_app()
        if choice == "1":
            try:
                webbrowser.open(self.clear_access.PRODUCT_URL)
            except Exception:
                return
        elif choice == "2":
            code = InputSafe.get_string("Enter Clear Access code:")
            if code:
                self.clear_access.set_code(code)
        elif choice == "3":
            self.clear_access.clear_code()

    def display_futures(self, view_label="1D"):
        """Renders categorized macro data inside a clean panel with Sparklines."""
        raw_data = self.yahoo.get_macro_snapshot(
            period=self.current_period,
            interval=self.current_interval
        )

        if not raw_data:
            missing = []
            try:
                missing = self.yahoo.get_last_missing_symbols()
            except Exception:
                pass

            msg = Text("Market data provider returned no rows. ", style="bold yellow")
            msg.append("This is usually a transient Yahoo/yfinance issue.\n", style="yellow")
            if missing:
                msg.append(f"\nSkipped symbols (no data): {', '.join(missing[:20])}", style="dim")
                if len(missing) > 20:
                    msg.append(f" (+{len(missing) - 20} more)", style="dim")

            return Panel(msg, border_style="yellow", title="[bold]Macro Dashboard[/bold]")

        # Define explicit category order
        cat_order = ["Indices", "Big Tech", "US Sectors", "Commodities", "FX", "Rates", "Crypto", "Macro ETFs"]

        def _sort_key(item):
            cat = item.get("category", "Other")
            sub = item.get("subcategory", "")
            tick = item.get("ticker", "")
            rank = cat_order.index(cat) if cat in cat_order else 999
            return (rank, sub, tick)

        raw_data.sort(key=_sort_key)

        table = Table(expand=True, box=box.MINIMAL_DOUBLE_HEAD)
        table.add_column("Trend", justify="center", width=5)
        # FORCE LEFT JUSTIFY HERE
        table.add_column("Ticker", style="cyan", justify="left")
        table.add_column("Price", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("% Chg", justify="right")
        table.add_column(f"Chart ({view_label})", justify="center", width=20, no_wrap=True)
        table.add_column("Vol", justify="right", style="dim")
        table.add_column("Security", min_width=20)

        current_cat = None
        current_subcat = None

        for item in raw_data:
            cat = item.get("category", "Other")
            subcat = item.get("subcategory", "")

            # 1. New Main Category?
            if cat != current_cat:
                table.add_row("", "", "", "", "", "", "", "") # Spacer
                table.add_row("", f"[bold underline gold1]{cat.upper()}[/bold underline gold1]", "", "", "", "", "", "")
                current_cat = cat
                current_subcat = None 

            # 2. New Sub Category?
            if subcat and subcat != current_subcat:
                # Removed leading spaces for flush-left alignment
                table.add_row("", f"[dim italic white]{subcat}[/dim italic white]", "", "", "", "", "", "")
                current_subcat = subcat

            change = float(item.get("change", 0.0) or 0.0)
            pct = float(item.get("pct", 0.0) or 0.0)
            c_color = "green" if change >= 0 else "red"

            trend_arrow = ChartRenderer.get_trend_arrow(change)
            history = item.get("history", []) or []
            sparkline = ChartRenderer.generate_sparkline(history, length=20)
            spark_color = "green" if (history and history[-1] >= history[0]) else ("red" if history else "dim")

            table.add_row(
                trend_arrow,
                item.get("ticker", ""),
                f"{float(item.get('price', 0.0) or 0.0):,.2f}",
                f"[{c_color}]{change:+.2f}[/{c_color}]",
                f"[{c_color}]{pct:+.2f}%[/{c_color}]",
                f"[{spark_color}]{sparkline}[/{spark_color}]",
                f"{int(item.get('volume', 0) or 0):,}",
                item.get("name", "")
            )

        missing = []
        try:
            missing = self.yahoo.get_last_missing_symbols()
        except Exception:
            pass

        footer = ""
        if missing:
            shown = ", ".join(missing[:12])
            footer = f"[dim]Skipped symbols (no data): {shown}" + ("…[/dim]" if len(missing) > 12 else "[/dim]")

        subtitle = f"[dim]Interval: {view_label} | Period: {self.current_period} | Bars: {self.current_interval}[/dim]"
        ticker_panel = Panel(
            Align.center(table),
            title=f"[bold gold1]MACRO DASHBOARD ([bold green]{view_label}[/bold green])[/bold gold1]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(0, 2),
            subtitle=subtitle if not footer else f"{subtitle}\n{footer}"
        )

        return ticker_panel

    def stock_lookup_loop(self):
        """
        Isolated loop for real-time stock ticker analysis.
        Allows interval switching specifically for the viewed ticker.
        """
        while True:
            # 1. Get Ticker
            ticker_input = self.console.input("\n[bold cyan]ENTER TICKER (or '0' to go back):[/bold cyan] ").strip().upper()
            
            if ticker_input == '0' or not ticker_input:
                break
            
            local_interval_idx = 0 
            
            # Inner Loop for interaction with THIS ticker
            while True:
                label, p, i = self.interval_options[local_interval_idx]
                
                self.console.print(f"[dim]Fetching {ticker_input} ({label})...[/dim]")
                
                # Fetch detailed data
                data = self.yahoo.get_detailed_quote(ticker_input, period=p, interval=i)

                if "error" in data:
                    self.console.print(f"[red]Error fetching {ticker_input}: {data['error']}[/red]")
                    break 

                # 2. Construct Robust Display
                change = data.get('change', 0.0)
                color = "green" if change >= 0 else "red"
                spark_color = color
                
                grid = Table.grid(expand=True, padding=(0, 2))
                grid.add_column(ratio=1)
                grid.add_column(ratio=2)
                
                stats_table = Table.grid(padding=(0, 2))
                stats_table.add_column(style="dim white")
                stats_table.add_column(style="bold white", justify="right")
                
                hist_data = data.get('history', [])
                open_price = hist_data[0] if hist_data else 0.0
                
                stats_table.add_row("Open", f"{open_price:,.2f}") 
                stats_table.add_row("High", f"{data.get('high', 0):,.2f}")
                stats_table.add_row("Low", f"{data.get('low', 0):,.2f}")
                stats_table.add_row("Volume", f"{data.get('volume', 0):,}")
                if data.get('mkt_cap'):
                    stats_table.add_row("Mkt Cap", f"{data['mkt_cap'] / 1e9:,.2f}B")
                stats_table.add_row("Sector", f"{data.get('sector', 'N/A')}")

                sparkline = ChartRenderer.generate_sparkline(hist_data, length=40)
                
                price_text = Text.assemble(
                    (f"${data.get('price', 0):,.2f}", "bold white"),
                    (f"  {data.get('change', 0):+.2f} ({data.get('pct', 0):+.2f}%)", f"bold {color}")
                )
                
                chart_panel = Panel(
                    Align.center(f"[{spark_color}]{sparkline}[/{spark_color}]"),
                    title=f"Trend ({label})",
                    border_style="dim"
                )

                grid.add_row(
                    stats_table,
                    Align.right(
                        Group(
                            Align.right(price_text), 
                            chart_panel
                        )
                    )
                )

                main_panel = Panel(
                    grid,
                    title=f"[bold gold1]{data.get('name', ticker_input)} ({ticker_input})[/bold gold1]",
                    subtitle=f"[dim]Interval: {label}[/dim]",
                    border_style="blue",
                    box=box.ROUNDED
                )
                
                self.console.clear()
                print("\x1b[3J", end="")
                self.console.print(main_panel)
                
                self.console.print("[bold cyan]OPTIONS:[/bold cyan] [I] Change Interval | [N] New Search | [0] Back")
                action = InputSafe.get_option(["i", "n", "0", "m", "x"], prompt_text="[>]").lower()

                if action == "i":
                    local_interval_idx = (local_interval_idx + 1) % len(self.interval_options)
                    continue 
                elif action == "n":
                    break 
                elif action == "0":
                    return
                elif action == "m":
                    return
                elif action == "x":
                    Navigator.exit_app()
