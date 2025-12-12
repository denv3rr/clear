from typing import Dict, Optional, Tuple, Any
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

    def get_quote_data(self, ticker: str) -> Dict[str, float]:
        """
        Fetches detailed quote data including Price and Day Change %.
        Returns: {'price': float, 'change_pct': float}
        """
        # 1. Check Finnhub first
        fh_quote = self.finnhub.get_quote(ticker)
        if fh_quote and 'price' in fh_quote and fh_quote['price'] > 0:
            return {
                "price": float(fh_quote['price']),
                "change_pct": float(fh_quote.get('percent', 0.0))
            }
        
        # 2. Fallback to Yahoo
        try:
            # Check macro list first
            data = self.yahoo.get_macro_snapshot()
            macro_item = next((item for item in data if item['ticker'] == ticker), None)
            
            if macro_item:
                return {
                    "price": macro_item['price'],
                    "change_pct": macro_item['pct']
                }
            
            # General Yahoo Lookup
            import yfinance as yf
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
                # Calculate change manually if needed, or assume 0 if open is missing
                try:
                    open_p = float(hist['Open'].iloc[-1])
                    change_pct = ((price - open_p) / open_p) * 100
                except:
                    change_pct = 0.0
                    
                return {"price": price, "change_pct": change_pct}

        except Exception:
            pass

        return {"price": 0.0, "change_pct": 0.0}

    def get_price(self, ticker: str) -> Optional[float]:
        """Legacy wrapper for simple price fetching."""
        data = self.get_quote_data(ticker)
        return data['price'] if data['price'] > 0 else None

    def calculate_portfolio_value(self, holdings: Dict[str, float]) -> Tuple[float, Dict[str, Dict[str, float]]]:
        """
        Calculates total value and returns detailed enrichment data.
        Returns: (total_value, {ticker: {'market_value': float, 'price': float, 'change_pct': float}})
        """
        total_value = 0.0
        enriched_holdings = {}
        
        for ticker, quantity in holdings.items():
            data = self.get_quote_data(ticker)
            price = data['price']
            
            if price > 0:
                market_value = price * quantity
                total_value += market_value
                
                enriched_holdings[ticker] = {
                    "market_value": market_value,
                    "price": price,
                    "change_pct": data['change_pct']
                }
            else:
                enriched_holdings[ticker] = {
                    "market_value": 0.0,
                    "price": 0.0,
                    "change_pct": 0.0
                }
                # console.print(f"[red]Warning: Could not price {ticker}.[/red]")
                
        return total_value, enriched_holdings