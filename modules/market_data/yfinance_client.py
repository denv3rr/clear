import yfinance as yf
import pandas as pd
import numpy as np

class YahooWrapper:
    """
    Handles fetching batch data for global macro assets using nested categorization.
    """
    
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
    def get_macro_snapshot(period="1d", interval="15m"):
        """
        Fetches intraday data and history for sparklines.
        
        Args:
            period (str): Yahoo finance period (1d, 5d, 1mo, etc.)
            interval (str): Yahoo finance interval (15m, 1h, 1d, etc.)
        """
        ticker_meta = {}
        for cat, symbols in YahooWrapper.MACRO_TICKERS.items():
            for sym, name in symbols.items():
                ticker_meta[sym] = {"name": name, "category": cat}
        
        flat_list = list(ticker_meta.keys())
        results = []

        try:
            # Download batch data
            # group_by='ticker' ensures we get a structured MultiIndex if we want it, 
            # but default is fine. We handle the structure below.
            data = yf.download(
                flat_list, 
                period=period, 
                interval=interval, 
                progress=False,
                group_by='column' # Keeps 'Close', 'Open' at top level
            )
            
            if data.empty: return []

            # Determine if we have a single ticker or multiple (affects DataFrame structure)
            is_single = len(flat_list) == 1

            for sym in flat_list:
                try:
                    meta = ticker_meta[sym]
                    
                    # Data Access Logic
                    if is_single:
                        # If single, data columns are just 'Close', 'Open' (no ticker level)
                        # We re-wrap it to mimic multi-index for consistent logic below,
                        # or just access directly. Let's access directly.
                        if 'Close' not in data.columns: continue
                        
                        closes = data['Close']
                        opens = data['Open']
                        highs = data['High']
                        lows = data['Low']
                        volumes = data['Volume']
                    else:
                        # Multi-ticker: data['Close'][sym]
                        if sym not in data['Close'].columns: continue
                        
                        closes = data['Close'][sym]
                        opens = data['Open'][sym]
                        highs = data['High'][sym]
                        lows = data['Low'][sym]
                        volumes = data['Volume'][sym]

                    # Clean scalar extraction (Last valid index)
                    # We drop NaNs to get the actual history for sparklines
                    valid_history = closes.dropna()
                    
                    if valid_history.empty:
                        continue

                    current = valid_history.iloc[-1]
                    # Get corresponding scalar values for the same index
                    last_idx = valid_history.index[-1]
                    
                    # Safe loc access
                    try:
                        open_p = opens.loc[last_idx]
                        high = highs.loc[last_idx]
                        low = lows.loc[last_idx]
                        volume = volumes.loc[last_idx]
                    except:
                        # Fallback if indices slightly mismatch
                        open_p = current 
                        high = current
                        low = current
                        volume = 0

                    # Calculate Change
                    # For '1d', change is relative to previous close usually, 
                    # but here we calculate relative to the Open of the *current bar* # or the *first bar* of the requested period?
                    # Yahoo usually gives 'change' relative to Prev Close.
                    # We will calculate change based on the period's first vs last for trends,
                    # or just Open vs Close of the last bar.
                    # Let's do: Current Price - Price (Start of Period) to show trend over the view.
                    
                    price_start = valid_history.iloc[0]
                    change = current - price_start
                    pct = (change / price_start) * 100 if price_start != 0 else 0.0

                    # Convert history series to list for sparkline
                    # Take last 20 points to ensure sparkline fits
                    history_list = valid_history.tail(30).tolist()

                    results.append({
                        "ticker": sym, 
                        "name": meta["name"], 
                        "category": meta["category"],
                        "price": float(current), 
                        "change": float(change), 
                        "pct": float(pct),
                        "high": float(high), 
                        "low": float(low), 
                        "volume": int(volume) if not pd.isna(volume) else 0,
                        "history": history_list # NEW FIELD
                    })
                except Exception:
                    continue
                    
        except Exception:
            return []

        return results