import os
import finnhub
import time
from rich.console import Console

class FinnhubWrapper:
    _CACHE = {}
    _TTL = 30  # 30 seconds

    def __init__(self):
        self.console = Console()
        self.api_key = os.getenv("FINNHUB_API_KEY")
        self.client = finnhub.Client(api_key=self.api_key) if self.api_key else None

    def _now(self):
        return int(time.time())

    def get_quote(self, symbol: str):
        """Fetches real-time quote for a single stock ticker with caching."""
        if not self.client:
            return {"error": "API Key Missing"}

        sym = symbol.upper()
        cache = FinnhubWrapper._CACHE.get(sym)
        if cache and (self._now() - cache[0]) < FinnhubWrapper._TTL:
            return cache[1]

        try:
            data = self.client.quote(sym)
            if data["c"] == 0 and data["d"] == 0:
                return None

            result = {
                "price": data["c"],
                "change": data["d"],
                "percent": data["dp"],
                "high": data["h"],
                "low": data["l"]
            }
            FinnhubWrapper._CACHE[sym] = (self._now(), result)
            return result
        except Exception:
            return None
