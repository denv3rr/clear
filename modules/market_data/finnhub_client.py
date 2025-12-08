import os
import finnhub
from rich.console import Console

class FinnhubWrapper:
    def __init__(self):
        self.console = Console()
        self.api_key = os.getenv("FINNHUB_API_KEY")
        self.client = None
        
        if self.api_key:
            self.client = finnhub.Client(api_key=self.api_key)

    def get_quote(self, symbol: str):
        """
        Fetches real-time quote for a single stock ticker.
        Returns a dict or None if failed.
        """
        if not self.client:
            return {"error": "API Key Missing"}

        try:
            # Finnhub 'quote' returns: c (current), d (change), dp (percent), etc.
            data = self.client.quote(symbol.upper())
            
            # Check if symbol exists (Finnhub often returns 0s for invalid tickers)
            if data['c'] == 0 and data['d'] == 0:
                return None
                
            return {
                "price": data['c'],
                "change": data['d'],
                "percent": data['dp'],
                "high": data['h'],
                "low": data['l']
            }
        except Exception as e:
            # We return None so the UI knows to display an error message
            return None