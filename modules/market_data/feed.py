from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box
from rich.text import Text
from rich.console import Group
from rich.layout import Layout

from utils.input import InputSafe
from modules.market_data.finnhub_client import FinnhubWrapper
from modules.market_data.yfinance_client import YahooWrapper
from utils.charts import ChartRenderer

class MarketFeed:
    def __init__(self):
        self.console = Console()
        self.finnhub = FinnhubWrapper()
        self.yahoo = YahooWrapper()
        
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
            self.console.clear()
            print("\x1b[3J", end="")
            
            # Display current settings in the view
            current_label = self.interval_options[self.interval_idx][0]
            
            self.display_futures(view_label=current_label)

            self.console.print("\n[bold gold1]MARKET ACTIONS MENU:[/bold gold1]")
            self.console.print("[1] 🔍 Ticker Search")
            self.console.print("[2] 🔄 Force Refresh")
            self.console.print(f"[3] 📅 Change Interval (Current: [cyan]{current_label}[/cyan])")
            self.console.print("[0] 🔙 Return to Main Menu")
            
            choice = InputSafe.get_option(["1", "2", "3", "0"], prompt_text="[>]")
            
            if choice == "0":
                self.console.clear()
                print("\x1b[3J", end="")
                break
            elif choice == "1":
                self.stock_lookup_loop()
            elif choice == "2":
                # Clear fast cache to force real refresh
                self.yahoo._FAST_CACHE.clear()
                continue 
            elif choice == "3":
                new_label = self.toggle_interval()

    def display_futures(self, view_label="1D"):
        """Renders categorized macro data inside a clean panel with Sparklines."""
        self.console.print(f"[dim]Fetching Global Data ({view_label})...[/dim]")

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

            self.console.print(Panel(msg, border_style="yellow", title="[bold]Macro Dashboard[/bold]"))
            return

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

        ticker_panel = Panel(
            Align.center(table),
            title=f"[bold gold1]MACRO DASHBOARD ([bold green]{view_label}[/bold green])[/bold gold1]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(0, 2),
            subtitle=footer
        )

        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print(ticker_panel)

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
                action = InputSafe.get_option(["i", "n", "0"], prompt_text="[>]").lower()

                if action == "i":
                    local_interval_idx = (local_interval_idx + 1) % len(self.interval_options)
                    continue 
                elif action == "n":
                    break 
                elif action == "0":
                    return
