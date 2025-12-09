from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box

from utils.input import InputSafe
from modules.market_data.finnhub_client import FinnhubWrapper
from modules.market_data.yfinance_client import YahooWrapper

class MarketFeed:
    def __init__(self):
        self.console = Console()
        self.finnhub = FinnhubWrapper()
        self.yahoo = YahooWrapper()

    def run(self):
        """Standard interaction loop for the Market Module."""
        while True:
            self.console.clear()
            self.display_futures()

            self.console.print("\n[bold gold1]MARKET ACTIONS MENU:[/bold gold1]")
            self.console.print("[1] 🔍 Quick Stock Lookup (Finnhub)")
            self.console.print("[2] 🔄 Force Refresh Macro Data")
            self.console.print("[0] 🔙 Return to Main Menu")
            
            choice = InputSafe.get_option(["1", "2", "0"], prompt_text="[>]")
            
            if choice == "0":
                self.console.clear()
                break
            elif choice == "1":
                self.stock_lookup_loop()
            elif choice == "2":
                continue 

    def display_futures(self):
        """Renders Categorized Futures and Macro data into an organized table with full intraday stats."""
        self.console.print("[dim]Fetching live global snapshot...[/dim]")
        raw_data = self.yahoo.get_macro_snapshot()

        if not raw_data:
            self.console.print("[red]Critical Error: Data stream unavailable.[/red]")
            return

        order = ["Commodities", "Indices", "FX", "Rates", "Crypto", "Macro ETFs"]
        raw_data.sort(key=lambda x: (order.index(x["category"]), x["ticker"]))

        table = Table(title="[bold blue]GLOBAL MACRO DASHBOARD[/bold blue]", 
                    expand=True, box=box.MINIMAL_DOUBLE_HEAD)
        
        # Column Layout
        table.add_column("Ticker", style="cyan")
        table.add_column("Price", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("% Chg", justify="right")
        table.add_column("Day High", justify="right", style="green")
        table.add_column("Day Low", justify="right", style="red")
        table.add_column("Volume", justify="right", style="dim")
        table.add_column("Security", style="white", min_width=20)

        current_cat = None
        for item in raw_data:
            if item["category"] != current_cat:
                table.add_row("", "", "", "", "", "", "", "") # Spacer
                table.add_row(
                    f"[bold underline gold1]{item['category'].upper()}[/bold underline gold1]", 
                    "", "", "", "", "", "", ""
                )
                current_cat = item["category"]

            c_color = "green" if item["change"] >= 0 else "red"
            
            table.add_row(
                item["ticker"],
                f"{item['price']:,.2f}",
                f"[{c_color}]{item['change']:+.2f}[/{c_color}]",
                f"[{c_color}]{item['pct']:+.2f}%[/{c_color}]",
                f"{item['high']:,.2f}",
                f"{item['low']:,.2f}",
                f"{item['volume']:,.0f}",
                item["name"]
            )

        self.console.print(table)

    def stock_lookup_loop(self):
        """Sub-loop for isolated real-time stock ticker analysis."""
        while True:
            ticker = self.console.input("\n[bold cyan]ENTER TICKER (or 'b' to go back):[/bold cyan] ").strip().upper()
            
            if ticker == 'B' or not ticker:
                break

            quote = self.finnhub.get_quote(ticker)

            # Check if quote is None or contains an error before proceeding
            if not quote or isinstance(quote, dict) and "error" in quote:
                if isinstance(quote, dict) and "error" in quote:
                    self.console.print(f"[red]{quote['error']}[/red]")
                else:
                    self.console.print(f"[red]Lookup Failed: Invalid ticker or data unavailable.[/red]")
                continue

            # Ensure the essential data for color calculation is present and not None
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