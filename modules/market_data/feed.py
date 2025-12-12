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

class MarketFeed:
    def __init__(self):
        self.console = Console()
        self.finnhub = FinnhubWrapper()
        self.yahoo = YahooWrapper()
        
        # Default View State
        self.current_period = "1d"
        self.current_interval = "15m"
        
        # Preset Intervals
        self.interval_options = [
            ("1D", "1d", "15m"),   # Label, Period, Interval
            ("5D", "5d", "60m"),
            ("1M", "1mo", "1d"),
            ("3M", "3mo", "1d"),
            ("1Y", "1y", "1wk")
        ]
        self.interval_idx = 0

    def _generate_sparkline(self, data: list, length: int = 40) -> str:
        """
        Converts a list of numerical values into a sparkline string.
        Uses blocks:  ▂▃▄▅▆▇█
        """
        if not data or len(data) < 2:
            return "─" * length
        
        # Slice data to fit desired length if necessary, or just use it all
        # For the detailed view, we might pass more data points
        display_data = data[-length:] if len(data) > length else data

        bars = u" ▂▃▄▅▆▇█"
        min_val = min(display_data)
        max_val = max(display_data)
        spread = max_val - min_val
        
        if spread == 0:
            return "─" * len(display_data)
            
        sparkline = ""
        for val in display_data:
            norm = (val - min_val) / spread
            idx = int(norm * (len(bars) - 1))
            sparkline += bars[idx]
            
        return sparkline

    def _get_trend_arrow(self, change: float) -> Text:
        """Returns a colored trend arrow based on change value."""
        if change > 0:
            return Text("▲", style="bold green")
        elif change < 0:
            return Text("▼", style="bold red")
        else:
            return Text("▶", style="dim white")

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
                break
            elif choice == "1":
                self.stock_lookup_loop()
            elif choice == "2":
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
            self.console.print("[red]Critical Error: Data stream unavailable.[/red]")
            return

        order = ["Commodities", "Indices", "FX", "Rates", "Crypto", "Macro ETFs"]
        raw_data.sort(key=lambda x: (order.index(x["category"]), x["ticker"]))

        table = Table(expand=True, box=box.MINIMAL_DOUBLE_HEAD)
        
        # Define Columns
        table.add_column("Trend", justify="center", width=5)
        table.add_column("Ticker", style="cyan")
        table.add_column("Price", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("% Chg", justify="right")
        table.add_column(f"Chart ({view_label})", justify="center", width=20, no_wrap=True)
        table.add_column("Vol", justify="right", style="dim")
        table.add_column("Security", min_width=20)

        current_cat = None
        for item in raw_data:

            if item["category"] != current_cat:
                table.add_row("", "", "", "", "", "", "", "")
                table.add_row(
                    "",
                    f"[bold underline gold1]{item['category'].upper()}[/bold underline gold1]",
                    "", "", "", "", "", ""
                )
                current_cat = item["category"]

            c_color = "green" if item["change"] >= 0 else "red"
            
            trend_arrow = self._get_trend_arrow(item["change"])
            # Generate sparkline with default length 20 for table
            sparkline = self._generate_sparkline(item["history"], length=20)
            
            spark_color = "green" if item["history"][-1] >= item["history"][0] else "red"

            table.add_row(
                trend_arrow,
                item["ticker"],
                f"{item['price']:,.2f}",
                f"[{c_color}]{item['change']:+.2f}[/{c_color}]",
                f"[{c_color}]{item['pct']:+.2f}%[/{c_color}]",
                f"[{spark_color}]{sparkline}[/{spark_color}]",
                f"{item['volume']:,.0f}",
                item["name"]
            )

        ticker_panel = Panel(
            Align.center(table),
            title=f"[bold gold1]MACRO DASHBOARD ({view_label})[/bold gold1]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(0, 2)
        )

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
            
            # Local state for this specific lookup
            local_interval_idx = 0 
            
            # Inner Loop for interaction with THIS ticker
            while True:
                label, p, i = self.interval_options[local_interval_idx]
                
                self.console.print(f"[dim]Fetching {ticker_input} ({label})...[/dim]")
                
                # Fetch detailed data
                data = self.yahoo.get_detailed_quote(ticker_input, period=p, interval=i)

                if "error" in data:
                    self.console.print(f"[red]Error fetching {ticker_input}: {data['error']}[/red]")
                    break # Break inner loop to ask for ticker again

                # 2. Construct Robust Display
                color = "green" if data['change'] >= 0 else "red"
                spark_color = color
                
                # Create a grid for the layout
                grid = Table.grid(expand=True, padding=(0, 2))
                grid.add_column(ratio=1)
                grid.add_column(ratio=2)
                
                # Left Side: Stats
                stats_table = Table.grid(padding=(0, 2))
                stats_table.add_column(style="dim white")
                stats_table.add_column(style="bold white", justify="right")
                
                stats_table.add_row("Open", f"{data['history'][0]:,.2f}") # Approx open of period
                stats_table.add_row("High", f"{data['high']:,.2f}")
                stats_table.add_row("Low", f"{data['low']:,.2f}")
                stats_table.add_row("Volume", f"{data['volume']:,}")
                if data.get('mkt_cap'):
                    stats_table.add_row("Mkt Cap", f"{data['mkt_cap'] / 1e9:,.2f}B")
                stats_table.add_row("Sector", f"{data['sector']}")

                # Right Side: Price & Chart
                # Generate a longer sparkline for detail view (e.g., 40 chars)
                sparkline = self._generate_sparkline(data['history'], length=40)
                
                price_text = Text.assemble(
                    (f"${data['price']:,.2f}", "bold white"),
                    (f"  {data['change']:+.2f} ({data['pct']:+.2f}%)", f"bold {color}")
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

                # Assemble Main Panel              
                main_panel = Panel(
                    grid,
                    title=f"[bold gold1]{data['name']} ({ticker_input})[/bold gold1]",
                    subtitle=f"[dim]Interval: {label}[/dim]",
                    border_style="blue",
                    box=box.ROUNDED
                )
                
                self.console.clear()
                self.console.print(main_panel)
                
                # 3. Lookup Menu
                self.console.print("[bold cyan]OPTIONS:[/bold cyan] [I] Change Interval | [N] New Search | [0] Back")
                action = InputSafe.get_option(["i", "n", "0"], prompt_text="[>]").lower()

                if action == "i":
                    # Toggle local interval only
                    local_interval_idx = (local_interval_idx + 1) % len(self.interval_options)
                    continue # Re-fetch with new interval
                elif action == "n":
                    break # Break inner loop, goes back to 'ENTER TICKER'
                elif action == "0":
                    return # Returns to MAIN MENU entirely