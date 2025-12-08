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

            self.console.print("\n[bold gold1]MARKET ACTIONS:[/bold gold1]")
            self.console.print("[1] 🔍 Quick Stock Lookup (Finnhub)")
            self.console.print("[2] 🔄 Force Refresh Macro Data")
            self.console.print("[0] 🔙 Return to Main Menu")
            
            choice = InputSafe.get_option(["1", "2", "0"], prompt_text="SELECT OPTION >")
            
            if choice == "0":
                break
            elif choice == "1":
                self.stock_lookup_loop()
            elif choice == "2":
                continue 

    def display_futures(self):
        """Renders Categorized Futures and Macro data into a organized table."""
        self.console.print("[dim]Fetching live global snapshot...[/dim]")
        raw_data = self.yahoo.get_macro_snapshot()

        if not raw_data:
            self.console.print("[red]Critical Error: Data stream unavailable.[/red]")
            return

        # Sort data based on custom category order to keep the UI consistent
        order = ["Commodities", "Indices", "FX", "Rates", "Crypto", "Macro ETFs"]
        raw_data.sort(key=lambda x: (order.index(x["category"]), x["ticker"]))

        table = Table(title="[bold blue]GLOBAL MACRO DASHBOARD[/bold blue]", 
                      expand=True, box=box.MINIMAL_DOUBLE_HEAD)
        
        table.add_column("Ticker", style="cyan")
        table.add_column("Security", style="white")
        table.add_column("Price", justify="right")
        table.add_column("Net Change", justify="right")
        table.add_column("% Change", justify="right")

        current_cat = None
        for item in raw_data:
            # Inject Category Header when a new category is reached
            if item["category"] != current_cat:
                table.add_row("", "", "", "", "") # Spacer
                table.add_row(
                    f"[bold underline gold1]{item['category'].upper()}[/bold underline gold1]", 
                    "", "", "", ""
                )
                current_cat = item["category"]

            c_color = "green" if item["change"] >= 0 else "red"
            
            table.add_row(
                item["ticker"],
                item["name"],
                f"{item['price']:,.2f}",
                f"[{c_color}]{item['change']:+.2f}[/{c_color}]",
                f"[{c_color}]{item['pct']:+.2f}%[/{c_color}]"
            )

        self.console.print(table)

    def stock_lookup_loop(self):
        """Sub-loop for isolated real-time stock ticker analysis."""
        while True:
            ticker = self.console.input("\n[bold cyan]ENTER TICKER (or 'b' to go back):[/bold cyan] ").strip().upper()
            
            if ticker == 'B' or not ticker:
                break
                
            quote = self.finnhub.get_quote(ticker)
            
            if not quote or "error" in quote:
                self.console.print(f"[red]Lookup Failed: Invalid ticker or API limitation.[/red]")
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