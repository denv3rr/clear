import yfinance as yf
import pandas as pd

class YahooWrapper:
    """
    Handles fetching batch data for global macro assets using nested categorization.
    """
    
    # Nested mapping for UI categorization and ticker lookup
    MACRO_TICKERS = {
        "Commodities": {
            "CL=F": "Crude Oil WTI", "BZ=F": "Brent Crude", "GC=F": "Gold", 
            "SI=F": "Silver", "HG=F": "Copper", "ZC=F": "Corn", "LE=F": "Live Cattle"
        },
        "Indices": {
            "^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "Nasdaq",
            "^VIX": "VIX Index", "^FTSE": "FTSE 100", "^N225": "Nikkei 225"
        },
        "FX": {
            "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY",
            "USDCAD=X": "USD/CAD", "USDMXN=X": "USD/MXN"
        },
        "Rates": {
            "^TNX": "10Y Treasury Yield", "^TYX": "30Y Treasury Yield", "^MOVE": "Bond Vol Index"
        },
        "Crypto": {
            "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana"
        },
        "Macro ETFs": {
            "BDRY": "Dry Bulk Ship ETF", "TLT": "20+Y Treasury ETF", "UUP": "Dollar ETF",
            "SPY": "S&P 500 ETF", "GLD": "Gold ETF"
        }
    }

    @staticmethod
    def get_macro_snapshot():
        """
        Flattens the categorized map, fetches data, and re-attaches categories.
        """
        ticker_meta = {}
        for cat, symbols in YahooWrapper.MACRO_TICKERS.items():
            for sym, name in symbols.items():
                ticker_meta[sym] = {"name": name, "category": cat}
        
        flat_list = list(ticker_meta.keys())
        results = []

        try:
            # Batch download 1 day of data
            data = yf.download(flat_list, period="1d", interval="1d", progress=False)
            
            if data.empty:
                return []

            for sym in flat_list:
                try:
                    meta = ticker_meta[sym]
                    
                    # Handle yfinance multi-index columns
                    current = data['Close'][sym].iloc[-1]
                    open_p = data['Open'][sym].iloc[-1]

                    change = current - open_p
                    pct = (change / open_p) * 100
                    
                    results.append({
                        "ticker": sym,
                        "name": meta["name"],
                        "category": meta["category"],
                        "price": float(current),
                        "change": float(change),
                        "pct": float(pct)
                    })
                except Exception:
                    continue # Skip individual tickers if they fail to parse
                    
        except Exception:
            return []

        return results