import math
import numpy as np
import pandas as pd
import yfinance as yf
import time
import io
import warnings
import contextlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn

from utils.input import InputSafe
from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.valuation import ValuationEngine

# Cache for CAPM computations to avoid redundant API calls
_CAPM_CACHE = {}  # key -> {"ts": int, "data": dict}
_CAPM_TTL_SECONDS = 900  # 15 minutes

# Suppress yfinance logs
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

class ModelSelector:
    """
    Logic engine that determines which financial models are appropriate
    based on client risk profile, account types, and asset classes.
    """
    @staticmethod
    def analyze_suitability(client: Client) -> List[str]:
        recommendations = []
        
        # 1. Analyze Account Types
        account_types = [a.account_type.lower() for a in client.accounts]
        has_derivatives = any("option" in t or "derivative" in t for t in account_types)
        has_crypto = any("crypto" in t for t in account_types)
        
        # 2. Analyze Holdings
        all_tickers = []
        for acc in client.accounts:
            all_tickers.extend(acc.holdings.keys())
            
        # 3. Generate Recommendations
        if has_derivatives:
            recommendations.append("Black-Scholes Option Pricing (Derivatives detected)")
        
        if has_crypto or client.risk_profile == "Aggressive":
            recommendations.append("Sortino Ratio (Downside volatility focus for high risk)")
        
        recommendations.append("CAPM (Capital Asset Pricing Model) - Standard Equity Baseline")
        
        return recommendations

class FinancialToolkit:
    """
    Advanced financial analysis tools context-aware of a specific client's portfolio.
    """
    def __init__(self, client: Client):
        self.client = client
        self.console = Console()
        self.valuation = ValuationEngine()
        self.benchmark_ticker = "SPY" # Using S&P 500 ETF as standard benchmark

    def run(self):
        """Main loop for the Client Financial Toolkit."""
        while True:
            self.console.clear()
            self.console.print(f"[bold gold1]FINANCIAL TOOLKIT | {self.client.name}[/bold gold1]")
            
            # --- AUTO MODEL SELECTION ---
            recs = ModelSelector.analyze_suitability(self.client)
            if recs:
                self.console.print(Panel(
                    "\n".join([f"• {r}" for r in recs]),
                    title="[bold green]Recommended Models[/bold green]",
                    border_style="green",
                    width=100
                ))
            
            self.console.print("\n[bold white]--- Quantitative Models ---[/bold white]")
            self.console.print("[1] 🔢 CAPM Analysis (Alpha, Beta, R²)")
            self.console.print("[2] 📉 Black-Scholes Option Pricing")
            self.console.print("[0] 🔙 Return to Client Dashboard")
            
            choice = InputSafe.get_option(["1", "2", "0"], prompt_text="[>]")
            
            if choice == "0":
                break
            elif choice == "1":
                self._run_capm_analysis()
            elif choice == "2":
                self._run_black_scholes()

    # --- REAL-TIME DATA ANALYSIS TOOLS ---

    def _run_capm_analysis(self):
        """
        Calculates Alpha and Beta by fetching 1y historical data for all holdings
        and the benchmark (SPY) using yfinance.
        """
        self.console.clear()
        self.console.print(f"[bold blue]CAPM & RISK METRICS (Benchmark: {self.benchmark_ticker})[/bold blue]")
        
        # 1. Aggregate Holdings
        consolidated_holdings = {}
        for acc in self.client.accounts:
            for ticker, qty in acc.holdings.items():
                consolidated_holdings[ticker] = consolidated_holdings.get(ticker, 0) + qty
        
        if not consolidated_holdings:
            self.console.print("[yellow]No holdings available for analysis.[/yellow]")
            InputSafe.pause()
            return

        tickers = list(consolidated_holdings.keys())
        
        # 2. Fetch Historical Data (with Progress Spinner)
        self.console.print("\nFetching historical market data from Yahoo Finance...")
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="Downloading 1-year price history...", total=None)
                
                # Download portfolio tickers + Benchmark
                download_list = tickers + [self.benchmark_ticker]
                data = yf.download(
                    download_list, 
                    period="1y", 
                    interval="1d", 
                    progress=False,
                    group_by='ticker',
                    auto_adjust=True
                )

        except Exception as e:
            self.console.print(f"[red]Error fetching market data: {e}[/red]")
            InputSafe.pause()
            return

        # 3. Process Data & Calculate Returns
        # Note: yf.download structure varies by version.
        #       Attempt to handle MultiIndex columns safely:
        try:
            # Create a clean DataFrame of Close prices
            close_prices = pd.DataFrame()
            
            for t in download_list:
                # Handle different yfinance return structures
                try:
                    if len(download_list) == 1:
                        # If only 1 ticker (rare here), data is flat
                        series = data['Close']
                    else:
                        # Access via MultiIndex level
                        series = data[t]['Close']
                    close_prices[t] = series
                except KeyError:
                    # Ticker might be delisted or crypto with different formatting
                    continue
            
            # Drop NaN rows to align dates
            close_prices.dropna(inplace=True)
            
            if close_prices.empty:
                self.console.print("[red]Insufficient historical data overlapping.[/red]")
                InputSafe.pause()
                return

            # Calculate Daily Returns (Percentage Change)
            daily_returns = close_prices.pct_change().dropna()
            
        except Exception as e:
            self.console.print(f"[red]Data processing error: {e}[/red]")
            InputSafe.pause()
            return

        # 4. Construct Synthetic Portfolio History
        # We assume current weights held constant over the period (Standard limitation of point-in-time analysis)
        
        # Calculate current weights based on latest price in the dataframe
        latest_prices = close_prices.iloc[-1]
        market_vals = {t: latest_prices[t] * consolidated_holdings[t] for t in tickers if t in latest_prices}
        total_mv = sum(market_vals.values())
        
        if total_mv == 0:
            self.console.print("[red]Total portfolio value is zero.[/red]")
            InputSafe.pause()
            return

        weights = {t: mv / total_mv for t, mv in market_vals.items()}
        
        # Calculate weighted portfolio return for each day
        portfolio_daily_ret = sum(daily_returns[t] * w for t, w in weights.items())
        benchmark_daily_ret = daily_returns[self.benchmark_ticker]

        # 5. Run Regression (Covariance / Variance)
        # Covariance(Portfolio, Market)
        covariance = np.cov(portfolio_daily_ret, benchmark_daily_ret)[0][1]
        variance = np.var(benchmark_daily_ret)
        
        beta = covariance / variance
        
        # Calculate Alpha (Annualized)
        # Avg Daily Return - (RiskFree + Beta * (Avg Market Return - RiskFree))
        # Assuming RFR ~ 4.0% annualized
        risk_free_daily = 0.04 / 252 
        
        avg_port_ret = np.mean(portfolio_daily_ret)
        avg_mkt_ret = np.mean(benchmark_daily_ret)
        
        alpha_daily = avg_port_ret - (risk_free_daily + beta * (avg_mkt_ret - risk_free_daily))
        alpha_annualized = alpha_daily * 252

        # R-Squared (Correlation Squared)
        correlation = np.corrcoef(portfolio_daily_ret, benchmark_daily_ret)[0][1]
        r_squared = correlation ** 2

        # --- DISPLAY RESULTS ---
        
        results = Table(title="CAPM Metrics (1 Year Lookback)", box=box.ROUNDED)
        results.add_column("Metric", style="bold white")
        results.add_column("Value", justify="right", style="bold cyan")
        results.add_column("Interpretation", style="italic dim")
        
        results.add_row("Beta", f"{beta:.2f}", "Volatility relative to S&P 500")
        results.add_row("Alpha (Annual)", f"{alpha_annualized:.2%}", "Excess return vs. risk taken")
        results.add_row("R-Squared", f"{r_squared:.2f}", "Correlation to benchmark")
        results.add_row("Sharpe (Est.)", f"{(avg_port_ret/np.std(portfolio_daily_ret)*(252**0.5)):.2f}", "Risk-adjusted return")

        self.console.print(Align.center(results))
        
        # Interpretation Logic
        if beta > 1.2:
            self.console.print("\n[bold yellow]⚠ High Volatility:[/bold yellow] This client portfolio is significantly more volatile than the market.")
        elif beta < 0.8:
            self.console.print("\n[bold green]🛡 Defensive:[/bold green] This client portfolio is less volatile than the market.")
            
        InputSafe.pause()

    def _run_black_scholes(self):
        """
        Calculates European Call/Put prices using Black-Scholes-Merton.
        Auto-fetches 'S' (Spot Price) if the user selects a holding.
        """
        self.console.clear()
        self.console.print(Panel("[bold]BLACK-SCHOLES DERIVATIVES MODEL[/bold]", box=box.HEAVY))
        
        # 1. Spot Price (S)
        ticker = self.console.input("[bold cyan]Underlying Ticker (Enter to skip lookup): [/bold cyan]").strip().upper()
        spot_price = 0.0
        
        if ticker:
            quote = self.valuation.get_quote_data(ticker)
            if quote['price'] > 0:
                spot_price = quote['price']
                self.console.print(f"   [green]✔ Live Spot Price ({ticker}): ${spot_price:,.2f}[/green]")
            else:
                self.console.print(f"   [yellow]⚠ Could not fetch price. Enter manually.[/yellow]")
        
        if spot_price == 0.0:
            spot_price = InputSafe.get_float("Enter Spot Price ($):", min_val=0.01)

        # 2. Strike Price (K)
        strike_price = InputSafe.get_float("Enter Strike Price ($):", min_val=0.01)

        # 3. Time to Maturity (T)
        days = InputSafe.get_float("Days to Expiration:", min_val=1)
        time_years = days / 365.0

        # 4. Volatility (sigma)
        volatility = InputSafe.get_float("Implied Volatility % (e.g. 25 for 25%):", min_val=0.01) / 100.0

        # 5. Risk Free Rate (r)
        risk_free = InputSafe.get_float("Risk-Free Rate % (e.g. 4.5):", min_val=0.0) / 100.0

        # --- CALCULATION ---
        d1 = (math.log(spot_price / strike_price) + (risk_free + 0.5 * volatility ** 2) * time_years) / (volatility * math.sqrt(time_years))
        d2 = d1 - volatility * math.sqrt(time_years)

        def N(x):
            return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

        call_price = spot_price * N(d1) - strike_price * math.exp(-risk_free * time_years) * N(d2)
        put_price = strike_price * math.exp(-risk_free * time_years) * N(-d2) - spot_price * N(-d1)

        # --- OUTPUT ---
        results = Table(title=f"Option Chain Valuation: {ticker if ticker else 'CUSTOM'}", box=box.ROUNDED)
        results.add_column("Metric", style="dim")
        results.add_column("Value", style="bold white")
        
        results.add_row("Underlying Price", f"${spot_price:.2f}")
        results.add_row("Strike Price", f"${strike_price:.2f}")
        results.add_row("Time (Years)", f"{time_years:.4f}")
        results.add_section()
        results.add_row("[bold green]CALL Value[/bold green]", f"[bold green]${call_price:.4f}[/bold green]")
        results.add_row("[bold red]PUT Value[/bold red]", f"[bold red]${put_price:.4f}[/bold red]")

        self.console.print("\n")
        self.console.print(Align.center(results))
        InputSafe.pause()
    
    @staticmethod
    def compute_capm_metrics_from_holdings(
        holdings: Dict[str, float],
        benchmark_ticker: str = "SPY",
        risk_free_annual: float = 0.04,
        period: str = "1y",
    ) -> Dict[str, Any]:
        """
        Computes CAPM + basic risk metrics for a portfolio represented by {ticker: qty}.
        Returns a dict; never raises in normal flows.

        Output keys:
        - beta, alpha_annual, r_squared, sharpe, vol_annual, points, error
        """
        ts = int(time.time())

        if not holdings:
            return {"error": "No holdings", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}

        # Cache key includes tickers+qty, benchmark, period, rf
        fp = tuple(sorted((str(k).upper(), round(float(v or 0.0), 6)) for k, v in holdings.items() if str(k).strip()))
        key = (fp, str(benchmark_ticker).upper(), period, float(risk_free_annual))

        cached = _CAPM_CACHE.get(key)
        if cached and (ts - int(cached.get("ts", 0))) <= _CAPM_TTL_SECONDS:
            return cached["data"]

        try:
            tickers = [t for t, q in fp if q != 0.0]
            if not tickers:
                data = {"error": "No non-zero holdings", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
                _CAPM_CACHE[key] = {"ts": ts, "data": data}
                return data

            download_list = sorted(set(tickers + [str(benchmark_ticker).upper()]))

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=FutureWarning)
                warnings.simplefilter("ignore", category=UserWarning)
                with contextlib.redirect_stderr(io.StringIO()):
                    df = yf.download(download_list, period=period, interval="1d", progress=False, group_by="column")
                    if df is None or df.empty:
                        data = {"error": "No market data returned", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
                        _CAPM_CACHE[key] = {"ts": ts, "data": data}
                        return data

            # Handle possible MultiIndex: prefer "Close"
            if isinstance(df.columns, pd.MultiIndex):
                if ("Close" in df.columns.levels[0]):
                    close = df["Close"].copy()
                elif ("Adj Close" in df.columns.levels[0]):
                    close = df["Adj Close"].copy()
                else:
                    data = {"error": "Close price not available", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
                    _CAPM_CACHE[key] = {"ts": ts, "data": data}
                    return data
            else:
                close = df.get("Close") or df.get("Adj Close")
                if close is None:
                    data = {"error": "Close price not available", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
                    _CAPM_CACHE[key] = {"ts": ts, "data": data}
                    return data

            bench = str(benchmark_ticker).upper()
            if bench not in close.columns:
                data = {"error": f"Benchmark '{bench}' missing", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
                _CAPM_CACHE[key] = {"ts": ts, "data": data}
                return data

            # Portfolio value series: sum(close[t] * qty)
            port_val = None
            for t, q in fp:
                if t == bench or q == 0.0:
                    continue
                if t not in close.columns:
                    continue
                series = close[t] * float(q)
                port_val = series if port_val is None else (port_val + series)

            if port_val is None:
                data = {"error": "No overlapping price series for holdings", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
                _CAPM_CACHE[key] = {"ts": ts, "data": data}
                return data

            port_ret = port_val.pct_change().dropna()
            mkt_ret = close[bench].pct_change().dropna()

            joined = pd.concat([port_ret.rename("p"), mkt_ret.rename("m")], axis=1).dropna()
            if joined.empty or len(joined) < 30:
                data = {"error": "Insufficient return history", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": int(len(joined))}
                _CAPM_CACHE[key] = {"ts": ts, "data": data}
                return data

            p = joined["p"].values
            m = joined["m"].values

            var_m = float(np.var(m, ddof=1))
            cov_pm = float(np.cov(p, m, ddof=1)[0][1])
            beta = (cov_pm / var_m) if var_m > 0 else None

            rf_daily = float(risk_free_annual) / 252.0
            avg_p = float(np.mean(p))
            avg_m = float(np.mean(m))

            alpha_daily = None
            alpha_annual = None
            if beta is not None:
                alpha_daily = avg_p - (rf_daily + beta * (avg_m - rf_daily))
                alpha_annual = alpha_daily * 252.0

            corr = float(np.corrcoef(p, m)[0][1])
            r_squared = corr * corr

            std_p = float(np.std(p, ddof=1))
            sharpe = ((avg_p - rf_daily) / std_p * (252.0 ** 0.5)) if std_p > 0 else None
            vol_annual = std_p * (252.0 ** 0.5)

            data = {
                "error": "",
                "beta": beta,
                "alpha_annual": alpha_annual,
                "r_squared": r_squared,
                "sharpe": sharpe,
                "vol_annual": vol_annual,
                "points": int(len(joined)),
                "benchmark": bench,
                "period": period,
                "risk_free_annual": float(risk_free_annual),
            }

            _CAPM_CACHE[key] = {"ts": ts, "data": data}
            return data

        except Exception as ex:
            data = {"error": f"CAPM compute error: {ex}", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
            _CAPM_CACHE[key] = {"ts": ts, "data": data}
            return data
