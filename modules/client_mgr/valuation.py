import concurrent.futures
from typing import Dict, Optional, Tuple, Any, List
from rich.console import Console

# Import the wrappers
from modules.market_data.finnhub_client import FinnhubWrapper
from modules.market_data.yfinance_client import YahooWrapper

class ValuationEngine:
    """
    Enhanced Valuation Engine with Threading for fast multi-asset retrieval.
    """

    def __init__(self):
        self.finnhub = FinnhubWrapper()
        self.yahoo = YahooWrapper()
        self.console = Console()

    def get_detailed_data(self, ticker: str) -> Dict[str, Any]:
        """
        Fetches comprehensive data (Price + History for Sparklines).
        Prioritizes Yahoo for history, falls back to Finnhub for real-time price.
        """
        # We primarily want Yahoo for the history lists needed for charts
        data = self.yahoo.get_detailed_quote(ticker, period="1mo", interval="1d")
        
        if "error" not in data:
            return data
            
        # Fallback to simple price if Yahoo fails (no chart data available)
        fh_quote = self.finnhub.get_quote(ticker)
        if fh_quote:
            return {
                "price": fh_quote['price'],
                "change": fh_quote['change'],
                "pct": fh_quote['percent'],
                "history": [], # No history from Finnhub free tier usually
                "mkt_cap": 0,
                "sector": "N/A"
            }
            
        return {"price": 0.0, "change": 0.0, "pct": 0.0, "history": []}

    def calculate_portfolio_value(self, holdings: Dict[str, float]) -> Tuple[float, Dict[str, Any]]:
        """
        THREADED calculation of portfolio value.
        Returns: (Total Value, Enriched Data Dictionary with History)
        """
        total_value = 0.0
        enriched_holdings = {}
        tickers = list(holdings.keys())

        # Use ThreadPoolExecutor to fetch all tickers in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_ticker = {executor.submit(self.get_detailed_data, t): t for t in tickers}
            
            for future in concurrent.futures.as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    qty = holdings[ticker]
                    price = data.get('price', 0.0)
                    
                    market_value = price * qty
                    total_value += market_value
                    
                    enriched_holdings[ticker] = {
                        "market_value": market_value,
                        "price": price,
                        "change": data.get('change', 0.0),
                        "pct": data.get('pct', 0.0),
                        "history": data.get('history', []),
                        "sector": data.get('sector', "N/A")
                    }
                except Exception as exc:
                    self.console.print(f"[red]Error fetching {ticker}: {exc}[/red]")
                    enriched_holdings[ticker] = {
                        "market_value": 0.0, "price": 0.0, "history": []
                    }

        return total_value, enriched_holdings

    def generate_synthetic_portfolio_history(self, enriched_data: Dict[str, Any], holdings: Dict[str, float]) -> List[float]:
        """
        Reconstructs the portfolio's aggregate history (for the main dashboard chart).
        Assumes historical length alignment (simple truncation method).
        """
        if not enriched_data:
            return []

        # Find the minimum history length available across all assets to ensure alignment
        histories = []
        for t, data in enriched_data.items():
            if data['history']:
                # Weighted history: Price * Quantity
                qty = holdings.get(t, 0)
                weighted_hist = [p * qty for p in data['history']]
                histories.append(weighted_hist)
        
        if not histories:
            return []

        min_len = min(len(h) for h in histories)
        if min_len == 0: return []

        # Sum up the history lists
        # We take the LAST 'min_len' items from each to align the most recent dates
        portfolio_history = [0.0] * min_len
        
        for h in histories:
            aligned_h = h[-min_len:]
            for i in range(min_len):
                portfolio_history[i] += aligned_h[i]
                
        return portfolio_history