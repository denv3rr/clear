import yfinance as yf
import pandas as pd

class YahooWrapper:
    """
    Handles fetching batch data for global macro assets using nested categorization.
    """
    
    # Nested mapping for UI categorization and ticker lookup (Expanded List)
    # Manually curate this main dashboard list per your needs...
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
        Fetches full intraday data (Open, Close, High, Low, Volume) for all categorized assets.
        """
        ticker_meta = {}
        for cat, symbols in YahooWrapper.MACRO_TICKERS.items():
            for sym, name in symbols.items():
                ticker_meta[sym] = {"name": name, "category": cat}
        
        flat_list = list(ticker_meta.keys())
        results = []

        try:
            # Setting progress=False to reduce terminal clutter
            data = yf.download(flat_list, period="1d", interval="1d", progress=False)
            
            if data.empty: return []

            # Check if yfinance returned a simple DataFrame (e.g., if only one ticker was requested)
            # which changes the column indexing from MultiIndex to simple keys.
            is_single_ticker_data = len(flat_list) == 1

            for sym in flat_list:
                try:
                    meta = ticker_meta[sym]
                    
                    # Robust check for data presence
                    if is_single_ticker_data:
                        # For single ticker, columns are just 'Open', 'Close', etc.
                        if 'Close' not in data.columns or pd.isna(data['Close'].iloc[-1]):
                            continue
                        current = data['Close'].iloc[-1]
                        open_p = data['Open'].iloc[-1]
                        high = data['High'].iloc[-1]
                        low = data['Low'].iloc[-1]
                        volume = data['Volume'].iloc[-1]
                    else:
                        # For multiple tickers (MultiIndex DataFrame)
                        if sym not in data['Close'].columns or pd.isna(data['Close'][sym].iloc[-1]):
                            continue
                        current = data['Close'][sym].iloc[-1]
                        open_p = data['Open'][sym].iloc[-1]
                        high = data['High'][sym].iloc[-1]
                        low = data['Low'][sym].iloc[-1]
                        volume = data['Volume'][sym].iloc[-1]
                    
                    # Ensure price and open are valid numbers for calculation
                    if current == 0.0 or open_p == 0.0:
                        # This handles cases where data is valid but the market is closed 
                        # and the last known price is the same as open, but volume is 0
                        change = 0.0
                        pct = 0.0
                    else:
                        change = current - open_p
                        pct = (change / open_p) * 100
                    
                    results.append({
                        "ticker": sym, "name": meta["name"], "category": meta["category"],
                        "price": float(current), "change": float(change), "pct": float(pct),
                        "high": float(high), "low": float(low), "volume": int(volume)
                    })
                except Exception:
                    # Skip assets that fail to parse (e.g., delisted or problematic tickers)
                    continue
                    
        except Exception:
            return []

        return results