import yfinance as yf
import pandas as pd
import numpy as np

class YahooWrapper:
    """
    Handles fetching batch data for global macro assets using nested categorization.
    """
    
    MACRO_TICKERS = {

        "Commodities": {
            # Energy
            "CL=F": "Crude Oil WTI",
            "BZ=F": "Brent Crude",
            "NG=F": "Natural Gas",
            "RB=F": "RBOB Gasoline",
            "HO=F": "Heating Oil",

            # Metals
            "GC=F": "Gold",
            "SI=F": "Silver",
            "HG=F": "Copper",
            "PL=F": "Platinum",
            "PA=F": "Palladium",

            # Agriculture
            "ZC=F": "Corn",
            "ZW=F": "Wheat",
            "ZS=F": "Soybeans",
            "KC=F": "Coffee",
            "SB=F": "Sugar",
            "CT=F": "Cotton",

            # Livestock
            "LE=F": "Live Cattle",
            "GF=F": "Feeder Cattle",
            "HE=F": "Lean Hogs"
        },

        "Indices": {
            # U.S.
            "^GSPC": "S&P 500",
            "^DJI": "Dow Jones",
            "^IXIC": "Nasdaq Composite",
            "^RUT": "Russell 2000",
            "^VIX": "VIX Volatility Index",

            # Europe
            "^FTSE": "FTSE 100",
            "^GDAXI": "DAX (Germany)",
            "^FCHI": "CAC 40 (France)",

            # Asia
            "^N225": "Nikkei 225",
            "^HSI": "Hang Seng Index",
            "^STI": "Singapore Straits Times",

            # Emerging Markets
            "^BVSP": "Bovespa (Brazil)",
            "^MXX": "IPC (Mexico)",
            "^KS11": "KOSPI (South Korea)"
        },

        "FX": {
            # Majors
            "EURUSD=X": "EUR/USD",
            "GBPUSD=X": "GBP/USD",
            "USDJPY=X": "USD/JPY",
            "AUDUSD=X": "AUD/USD",
            "NZDUSD=X": "NZD/USD",

            # USD crosses
            "USDCAD=X": "USD/CAD",
            "USDCHF=X": "USD/CHF",
            "USDSEK=X": "USD/SEK",
            "USDNOK=X": "USD/NOK",
            "USDZAR=X": "USD/ZAR",

            # EM FX
            "USDMXN=X": "USD/MXN",
            "USDTRY=X": "USD/TRY",
            "USDCNY=X": "USD/CNY",
            "USDHKD=X": "USD/HKD",
            "USDINR=X": "USD/INR"
        },

        "Rates": {
            # U.S. yields
            "^IRX": "13W Treasury Bill Yield",
            "^FVX": "5Y Treasury Yield",
            "^TNX": "10Y Treasury Yield",
            "^TYX": "30Y Treasury Yield",

            # Volatility indices
            "^MOVE": "Bond Volatility Index",

            # Global rates (confirmed)
            "^FTSE": "UK 10Y Gilt Yield",
            "^N225": "Japan 10Y JGB Yield"
        },

        "Crypto": {
            "BTC-USD": "Bitcoin",
            "ETH-USD": "Ethereum",
            "SOL-USD": "Solana",
            "XRP-USD": "Ripple",
            "ADA-USD": "Cardano"
        },

        "Macro ETFs": {
            # Equities
            "SPY": "S&P 500 ETF",
            "QQQ": "Nasdaq 100 ETF",
            "IWM": "Russell 2000 ETF",

            # Global macro exposures
            "EEM": "Emerging Markets ETF",
            "VEA": "Developed Markets ex-US ETF",

            # Rates & Credit
            "TLT": "20+ Year Treasury Bond ETF",
            "IEF": "7–10 Year Treasury ETF",
            "HYG": "High Yield Corporate Bond ETF",
            "LQD": "Investment Grade Corporate Bond ETF",

            # Currencies
            "UUP": "US Dollar Index ETF",
            "FXE": "Euro Currency ETF",
            "FXY": "Japanese Yen ETF",

            # Commodities
            "GLD": "Gold ETF",
            "SLV": "Silver ETF",
            "DBC": "Broad Commodity ETF",
            "USO": "Oil ETF",

            # Shipping & global trade
            "BDRY": "Dry Bulk Shipping ETF",
            "SEA": "Global Shipping ETF"
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
            data = yf.download(
                flat_list, 
                period=period, 
                interval=interval, 
                progress=False,
                group_by='column' 
            )
            
            if data.empty: return []

            is_single = len(flat_list) == 1

            for sym in flat_list:
                try:
                    meta = ticker_meta[sym]
                    
                    if is_single:
                        if 'Close' not in data.columns: continue
                        closes = data['Close']
                        opens = data['Open']
                        highs = data['High']
                        lows = data['Low']
                        volumes = data['Volume']
                    else:
                        if sym not in data['Close'].columns: continue
                        closes = data['Close'][sym]
                        opens = data['Open'][sym]
                        highs = data['High'][sym]
                        lows = data['Low'][sym]
                        volumes = data['Volume'][sym]

                    valid_history = closes.dropna()
                    
                    if valid_history.empty:
                        continue

                    current = valid_history.iloc[-1]
                    last_idx = valid_history.index[-1]
                    
                    try:
                        open_p = opens.loc[last_idx]
                        high = highs.loc[last_idx]
                        low = lows.loc[last_idx]
                        volume = volumes.loc[last_idx]
                    except:
                        open_p = current 
                        high = current
                        low = current
                        volume = 0
                    
                    price_start = valid_history.iloc[0]
                    change = current - price_start
                    pct = (change / price_start) * 100 if price_start != 0 else 0.0

                    # FIX: Reduced to 20 points to match the UI column width
                    history_list = valid_history.tail(20).tolist()

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
                        "history": history_list
                    })
                except Exception:
                    continue
                    
        except Exception:
            return []

        return results