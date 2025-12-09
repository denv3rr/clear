from typing import Dict, Optional, Tuple
from rich.console import Console

# Import the data wrappers
from modules.market_data.finnhub_client import FinnhubWrapper
from modules.market_data.yfinance_client import YahooWrapper

console = Console()

class ValuationEngine:
    """
    Combines Finnhub and Yahoo to get comprehensive pricing for portfolio holdings.
    Finnhub is prioritized for standard stocks; Yahoo for macro assets and fallbacks.
    """

    def __init__(self):
        self.finnhub = FinnhubWrapper()
        self.yahoo = YahooWrapper()

    def get_price(self, ticker: str) -> Optional[float]:
        """
        Attempts to get the current price for a ticker.
        Priority: Finnhub (best quote) -> Yahoo (macro list) -> Yahoo (general lookup).
        
        Returns: current price as float or None.
        """
        # 1. Check Finnhub first (best for stocks/ETFs if API key is valid)
        fh_quote = self.finnhub.get_quote(ticker)
        if fh_quote and 'price' in fh_quote and fh_quote['price'] > 0:
            return fh_quote['price']
        
        # 2. Fallback to Yahoo (Check macro list first to avoid general lookup overhead)
        try:
            # We assume a direct ticker exists in the macro list if it's there
            data = self.yahoo.get_macro_snapshot()
            price_data = next((item for item in data if item['ticker'] == ticker), None)
            
            if price_data:
                return price_data['price']
            
            # 3. Final Fallback: General Yahoo Finance lookup
            import yfinance as yf
            stock = yf.Ticker(ticker)
            # Use safe lookup for last close price
            price = stock.history(period="1d")['Close'].iloc[-1]
            return float(price)

        except Exception:
            # Ticker not found, data unavailable, or network error
            return None

    def calculate_portfolio_value(self, holdings: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
        """
        Calculates the total market value of a dictionary of holdings {ticker: quantity}.
        
        Returns: (total_value, {ticker: market_value})
        """
        total_value = 0.0
        valued_holdings = {}
        
        # console.print("[dim]Valuing portfolio holdings...[/dim]")
        
        for ticker, quantity in holdings.items():
            price = self.get_price(ticker)
            
            if price is not None:
                market_value = price * quantity
                total_value += market_value
                valued_holdings[ticker] = market_value
            else:
                valued_holdings[ticker] = 0.0
                console.print(f"[red]Warning: Could not price {ticker}. Value set to $0.00.[/red]")
                
        return total_value, valued_holdings