from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box
from rich.text import Text

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

    def _generate_sparkline(self, data: list) -> str:
        """
        Converts a list of numerical values into a sparkline string.
        Uses blocks:  ▂▃▄▅▆▇█
        """
        if not data or len(data) < 2:
            return "─" * len(data) if data else "─" * 20
        
        bars = u" ▂▃▄▅▆▇█"
        min_val = min(data)
        max_val = max(data)
        spread = max_val - min_val
        
        if spread == 0:
            return "─" * len(data)
            
        sparkline = ""
        for val in data:
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
        # Increased width to 20 and added no_wrap to prevent ellipsis
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
            sparkline = self._generate_sparkline(item["history"])
            
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
        """Sub-loop for isolated real-time stock ticker analysis."""
        while True:
            ticker = self.console.input("\n[bold cyan]ENTER TICKER (or 'b' to go back):[/bold cyan] ").strip().upper()
            
            if ticker == 'B' or not ticker:
                break

            quote = self.finnhub.get_quote(ticker)

            if not quote or isinstance(quote, dict) and "error" in quote:
                if isinstance(quote, dict) and "error" in quote:
                    self.console.print(f"[red]{quote['error']}[/red]")
                else:
                    self.console.print(f"[red]Lookup Failed: Invalid ticker or data unavailable.[/red]")
                continue

            if quote.get('change') is None:
                self.console.print(f"[red]Lookup Failed: Data unavailable for '{ticker}'.[/red]")
                continue

            color = "green" if quote['change'] >= 0 else "red"

            p = Panel(
                f"[bold white]Price:[/bold white] ${quote['price']:,.2f}\n"
                f"[bold white]Change:[/bold white] [{color}]{quote['change']:+.2f} ({quote['percent']:+.2f}%) [/{color}]\n"
                f"[dim]Range: {quote['low']:,.2f} - {quote['high']:,.2f}[/dim]",
                title=f"[bold gold1]{ticker}[/bold gold1]",
                border_style="blue"
            )
            self.console.print(p)