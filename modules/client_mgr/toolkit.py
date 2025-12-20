import math
import numpy as np
import pandas as pd
import yfinance as yf
import time
import io
import warnings
import contextlib
import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from rich.console import Console, Group
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

# Interval presets for toolkit models
TOOLKIT_PERIOD = {"1W": "1mo", "1M": "6mo", "3M": "1y", "6M": "2y", "1Y": "5y"}
TOOLKIT_INTERVAL = {"1W": "60m", "1M": "1d", "3M": "1d", "6M": "1d", "1Y": "1d"}

# Suppress yfinance logs
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# REGIME SNAPSHOT CONTRACT
# ---------------------------------------------------------------------------
# The UI consumes this structure only.
# The underlying model (Markov / HMM / etc.) must conform to this output.
#
# {
#   "model": "Markov",
#   "horizon": "1D",
#   "current_regime": str,
#   "confidence": float,
#   "state_probs": dict[str, float],
#   "transition_matrix": list[list[float]],
#   "expected_next": {"regime": str, "probability": float},
#   "stability": float,
#   "metrics": {"avg_return": float, "volatility": float}
# }
# ---------------------------------------------------------------------------

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
            print("\x1b[3J", end="")
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
            self.console.print("[3] 📊 Multi-Model Risk Dashboard")
            self.console.print("[4] 🎲 Monte Carlo Simulation")
            self.console.print("[0] 🔙 Return to Client Dashboard")
            
            choice = InputSafe.get_option(["1", "2", "3", "4", "0"], prompt_text="[>]")
            
            if choice == "0":
                break
            elif choice == "1":
                self._run_capm_analysis()
            elif choice == "2":
                self._run_black_scholes()
            elif choice == "3":
                self._run_multi_model_dashboard()
            elif choice == "4":
                self._run_monte_carlo()

    # --- REAL-TIME DATA ANALYSIS TOOLS ---

    def _run_capm_analysis(self):
        """
        Calculates Alpha and Beta by fetching 1y historical data for all holdings
        and the benchmark (SPY) using yfinance.
        """
        self.console.clear()
        print("\x1b[3J", end="")
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
        print("\x1b[3J", end="")
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

    def _run_multi_model_dashboard(self):
        """Compute a multi-model risk dashboard for the client's portfolio."""
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print(f"[bold blue]MULTI-MODEL RISK DASHBOARD[/bold blue]")

        interval = self._select_interval()
        if not interval:
            return

        holdings = self._aggregate_holdings()
        if not holdings:
            self.console.print("[yellow]No holdings available for analysis.[/yellow]")
            InputSafe.pause()
            return

        period = TOOLKIT_PERIOD.get(interval, "1y")
        returns, benchmark_returns, meta = self._get_portfolio_and_benchmark_returns(
            holdings,
            benchmark_ticker=self.benchmark_ticker,
            period=period,
            interval=TOOLKIT_INTERVAL.get(interval, "1d"),
        )

        if returns is None or returns.empty:
            self.console.print("[yellow]Insufficient market data for this interval.[/yellow]")
            InputSafe.pause()
            return

        metrics = self._compute_risk_metrics(
            returns,
            benchmark_returns=benchmark_returns,
            risk_free_annual=0.04,
        )

        title = f"[bold gold1]Portfolio Risk Models[/bold gold1] [dim]({interval})[/dim]"
        header = Panel(
            Align.center(f"[bold white]{self.client.name}[/bold white] | [dim]{meta}[/dim]"),
            title=title,
            border_style="cyan",
            box=box.ROUNDED,
        )
        self.console.print(header)
        self.console.print(self._render_risk_metrics_table(metrics))
        self.console.print(self._render_return_distribution(returns))
        InputSafe.pause()

    def _run_monte_carlo(self):
        """Run a Monte Carlo simulation for portfolio growth."""
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print("[bold blue]MONTE CARLO SIMULATION[/bold blue]")

        interval = self._select_interval()
        if not interval:
            return

        holdings = self._aggregate_holdings()
        if not holdings:
            self.console.print("[yellow]No holdings available for simulation.[/yellow]")
            InputSafe.pause()
            return

        sim_count = int(InputSafe.get_float("Number of simulations:", min_val=100))
        horizon_days = int(InputSafe.get_float("Horizon (trading days):", min_val=10))
        use_t = InputSafe.get_yes_no("Use Student-t shocks? (y/n):")
        df_t = 6.0
        if use_t:
            df_t = InputSafe.get_float("Degrees of freedom (e.g. 6):", min_val=2)

        period = TOOLKIT_PERIOD.get(interval, "1y")
        returns, benchmark_returns, meta = self._get_portfolio_and_benchmark_returns(
            holdings,
            benchmark_ticker=self.benchmark_ticker,
            period=period,
            interval=TOOLKIT_INTERVAL.get(interval, "1d"),
        )
        if returns is None or returns.empty:
            self.console.print("[yellow]Insufficient market data for this interval.[/yellow]")
            InputSafe.pause()
            return

        mu = float(returns.mean())
        sigma = float(returns.std(ddof=1))
        if sigma <= 0:
            self.console.print("[yellow]Volatility is zero; simulation not meaningful.[/yellow]")
            InputSafe.pause()
            return

        sims = self._simulate_monte_carlo(
            mu=mu,
            sigma=sigma,
            horizon=horizon_days,
            n_sims=sim_count,
            use_t=use_t,
            df_t=float(df_t),
        )

        title = f"[bold gold1]Monte Carlo Paths[/bold gold1] [dim]({interval})[/dim]"
        header = Panel(
            Align.center(f"[bold white]{self.client.name}[/bold white] | [dim]{meta}[/dim]"),
            title=title,
            border_style="magenta",
            box=box.ROUNDED,
        )
        self.console.print(header)
        self.console.print(self._render_monte_carlo_summary(sims))
        self.console.print(self._render_monte_carlo_percentiles(sims))
        InputSafe.pause()

    def _select_interval(self) -> Optional[str]:
        options = list(TOOLKIT_PERIOD.keys())
        self.console.print("\n[bold white]Select Interval[/bold white]")
        for opt in options:
            self.console.print(f"[{opt}]")
        choice = InputSafe.get_option(options, prompt_text="[>]")
        return choice.upper()

    def _aggregate_holdings(self) -> Dict[str, float]:
        consolidated = {}
        for acc in self.client.accounts:
            for ticker, qty in acc.holdings.items():
                consolidated[ticker] = consolidated.get(ticker, 0) + qty
        return consolidated

    def _get_portfolio_and_benchmark_returns(
        self,
        holdings: Dict[str, float],
        benchmark_ticker: str,
        period: str,
        interval: str,
    ) -> Tuple[Optional[pd.Series], Optional[pd.Series], str]:
        tickers = [t for t, q in holdings.items() if str(t).strip() and float(q or 0.0) != 0.0]
        if not tickers:
            return None, None, "No non-zero holdings"

        download_list = sorted(set([str(t).upper() for t in tickers] + [benchmark_ticker]))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=FutureWarning)
                warnings.simplefilter("ignore", category=UserWarning)
                with contextlib.redirect_stderr(io.StringIO()):
                    df = yf.download(
                        download_list,
                        period=period,
                        interval=interval,
                        progress=False,
                        group_by="column",
                        auto_adjust=True,
                    )
        except Exception as exc:
            return None, None, f"Market data error: {exc}"

        if df is None or df.empty:
            return None, None, "Market data empty"

        if isinstance(df.columns, pd.MultiIndex):
            if "Close" in df.columns.levels[0]:
                close = df["Close"].copy()
            elif "Adj Close" in df.columns.levels[0]:
                close = df["Adj Close"].copy()
            else:
                return None, None, "Close price not available"
        else:
            close = df.get("Close") or df.get("Adj Close")
            if close is None:
                return None, None, "Close price not available"

        bench = str(benchmark_ticker).upper()
        if bench not in close.columns:
            return None, None, f"Benchmark '{bench}' missing"

        port_val = None
        for t, qty in holdings.items():
            t_norm = str(t).upper()
            if t_norm == bench or t_norm not in close.columns:
                continue
            series = close[t_norm] * float(qty)
            port_val = series if port_val is None else (port_val + series)

        if port_val is None:
            return None, None, "No overlapping price series"

        port_ret = port_val.pct_change().dropna()
        bench_ret = close[bench].pct_change().dropna()
        meta = f"Period: {period} | Interval: {interval} | Points: {len(port_ret)}"
        return port_ret, bench_ret, meta

    def _compute_risk_metrics(
        self,
        returns: pd.Series,
        benchmark_returns: Optional[pd.Series],
        risk_free_annual: float,
    ) -> Dict[str, Any]:
        ann_factor = 252.0
        rf_daily = risk_free_annual / ann_factor
        avg_daily = float(returns.mean())
        std_daily = float(returns.std(ddof=1))

        vol_annual = std_daily * (ann_factor ** 0.5)
        mean_annual = avg_daily * ann_factor

        sharpe = None
        if std_daily > 0:
            sharpe = (avg_daily - rf_daily) / std_daily * (ann_factor ** 0.5)

        downside = returns[returns < rf_daily]
        downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
        sortino = None
        if downside_std > 0:
            sortino = (avg_daily - rf_daily) / downside_std * (ann_factor ** 0.5)

        beta = None
        alpha_annual = None
        r_squared = None
        information_ratio = None
        treynor = None
        m_squared = None
        tracking_error = None

        if benchmark_returns is not None and not benchmark_returns.empty:
            aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
            if not aligned.empty and len(aligned) > 10:
                p = aligned.iloc[:, 0].values
                m = aligned.iloc[:, 1].values
                var_m = float(np.var(m, ddof=1))
                cov_pm = float(np.cov(p, m, ddof=1)[0][1])
                beta = (cov_pm / var_m) if var_m > 0 else None

                avg_m = float(np.mean(m))
                alpha_annual = (avg_daily - (rf_daily + (beta or 0.0) * (avg_m - rf_daily))) * ann_factor

                corr = float(np.corrcoef(p, m)[0][1])
                r_squared = corr * corr

                excess = p - m
                tracking_error = float(np.std(excess, ddof=1))
                if tracking_error > 0:
                    information_ratio = (avg_daily - avg_m) / tracking_error * (ann_factor ** 0.5)

                if beta and beta != 0:
                    treynor = (avg_daily - rf_daily) / beta * ann_factor

                std_m = float(np.std(m, ddof=1))
                if std_daily > 0:
                    m_squared = ((avg_daily - rf_daily) / std_daily) * std_m * ann_factor + risk_free_annual

        max_drawdown = self._max_drawdown(returns)
        var_95, cvar_95 = self._historical_var_cvar(returns, 0.95)
        var_99, cvar_99 = self._historical_var_cvar(returns, 0.99)

        return {
            "mean_annual": mean_annual,
            "vol_annual": vol_annual,
            "sharpe": sharpe,
            "sortino": sortino,
            "beta": beta,
            "alpha_annual": alpha_annual,
            "r_squared": r_squared,
            "information_ratio": information_ratio,
            "tracking_error": tracking_error,
            "treynor": treynor,
            "m_squared": m_squared,
            "max_drawdown": max_drawdown,
            "var_95": var_95,
            "cvar_95": cvar_95,
            "var_99": var_99,
            "cvar_99": cvar_99,
        }

    def _max_drawdown(self, returns: pd.Series) -> float:
        if returns.empty:
            return 0.0
        cumulative = (1 + returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative / peak) - 1.0
        return float(drawdown.min())

    def _historical_var_cvar(self, returns: pd.Series, confidence: float) -> Tuple[float, float]:
        if returns.empty:
            return 0.0, 0.0
        q = returns.quantile(1 - confidence)
        tail = returns[returns <= q]
        cvar = float(tail.mean()) if not tail.empty else float(q)
        return float(q), cvar

    def _render_risk_metrics_table(self, metrics: Dict[str, Any]) -> Panel:
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", justify="right")
        table.add_column("Notes", style="dim")

        def fmt(value: Any, fmt_str: str, fallback: str = "N/A") -> str:
            return fallback if value is None else fmt_str.format(value)

        table.add_row("Annual Return (μ)", fmt(metrics.get("mean_annual"), "{:+.2%}"), "Avg daily return * 252")
        table.add_row("Volatility (σ)", fmt(metrics.get("vol_annual"), "{:.2%}"), "Annualized std dev")
        table.add_row("Sharpe Ratio", fmt(metrics.get("sharpe"), "{:.2f}"), "Risk-adjusted return")
        table.add_row("Sortino Ratio", fmt(metrics.get("sortino"), "{:.2f}"), "Downside-adjusted")
        table.add_row("Beta", fmt(metrics.get("beta"), "{:.2f}"), "Systemic sensitivity")
        table.add_row("Alpha (Jensen)", fmt(metrics.get("alpha_annual"), "{:+.2%}"), "Excess return vs CAPM")
        table.add_row("R-Squared", fmt(metrics.get("r_squared"), "{:.2f}"), "Fit vs benchmark")
        table.add_row("Tracking Error", fmt(metrics.get("tracking_error"), "{:.2%}"), "Std dev of excess")
        table.add_row("Information Ratio", fmt(metrics.get("information_ratio"), "{:.2f}"), "Excess / tracking error")
        table.add_row("Treynor Ratio", fmt(metrics.get("treynor"), "{:.2%}"), "Return per beta")
        table.add_row("M²", fmt(metrics.get("m_squared"), "{:+.2%}"), "Modigliani-Modigliani")
        table.add_row("Max Drawdown", fmt(metrics.get("max_drawdown"), "{:.2%}"), "Peak-to-trough")
        table.add_row("VaR 95%", fmt(metrics.get("var_95"), "{:+.2%}"), "Historical quantile")
        table.add_row("CVaR 95%", fmt(metrics.get("cvar_95"), "{:+.2%}"), "Expected tail loss")
        table.add_row("VaR 99%", fmt(metrics.get("var_99"), "{:+.2%}"), "Historical quantile")
        table.add_row("CVaR 99%", fmt(metrics.get("cvar_99"), "{:+.2%}"), "Expected tail loss")

        return Panel(table, title="[bold]Model Metrics[/bold]", box=box.ROUNDED, border_style="blue")

    def _render_return_distribution(self, returns: pd.Series) -> Panel:
        bins = [-0.10, -0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05, 0.10]
        labels = ["<-10%", "-10~-5%", "-5~-2%", "-2~-1%", "-1~0%", "0~1%", "1~2%", "2~5%", "5~10%", ">10%"]
        counts = [0] * (len(bins) + 1)

        for r in returns:
            idx = 0
            while idx < len(bins) and r > bins[idx]:
                idx += 1
            counts[idx] += 1

        max_count = max(counts) if counts else 1

        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Bucket", style="bold white")
        table.add_column("Freq", justify="right")
        table.add_column("Distribution", justify="left")

        for label, count in zip(labels, counts):
            intensity = count / max_count if max_count > 0 else 0
            blocks = int(round(intensity * 24))
            blocks = max(1, blocks) if count > 0 else 0
            color = "red" if label.startswith("-") or label.startswith("<") else "green"
            bar = "█" * blocks if blocks > 0 else "·"
            table.add_row(label, f"{count}", f"[{color}]{bar}[/{color}]")

        return Panel(table, title="[bold]Return Distribution[/bold] [dim](3D Bucket View)[/dim]", box=box.ROUNDED, border_style="magenta")

    def _simulate_monte_carlo(
        self,
        mu: float,
        sigma: float,
        horizon: int,
        n_sims: int,
        use_t: bool,
        df_t: float,
    ) -> np.ndarray:
        if use_t:
            shocks = np.random.standard_t(df_t, size=(n_sims, horizon))
            shocks = shocks / np.sqrt(df_t / (df_t - 2.0))
        else:
            shocks = np.random.standard_normal(size=(n_sims, horizon))

        returns = mu + sigma * shocks
        paths = np.cumprod(1.0 + returns, axis=1)
        return paths

    def _render_monte_carlo_summary(self, sims: np.ndarray) -> Panel:
        terminal = sims[:, -1]
        mean = float(np.mean(terminal))
        median = float(np.median(terminal))
        p10 = float(np.percentile(terminal, 10))
        p90 = float(np.percentile(terminal, 90))

        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", justify="right")
        table.add_column("Notes", style="dim")

        table.add_row("Terminal Mean", f"{mean:,.3f}x", "Expected multiple")
        table.add_row("Terminal Median", f"{median:,.3f}x", "Median multiple")
        table.add_row("10th Percentile", f"{p10:,.3f}x", "Downside")
        table.add_row("90th Percentile", f"{p90:,.3f}x", "Upside")

        return Panel(table, title="[bold]Simulation Summary[/bold]", box=box.ROUNDED, border_style="blue")

    def _render_monte_carlo_percentiles(self, sims: np.ndarray) -> Panel:
        horizon = sims.shape[1]
        steps = [0, horizon // 4, horizon // 2, (3 * horizon) // 4, horizon - 1]
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Step", style="bold white")
        table.add_column("P10", justify="right")
        table.add_column("P50", justify="right")
        table.add_column("P90", justify="right")
        table.add_column("Distribution", justify="left")

        for step in steps:
            slice_vals = sims[:, step]
            p10 = float(np.percentile(slice_vals, 10))
            p50 = float(np.percentile(slice_vals, 50))
            p90 = float(np.percentile(slice_vals, 90))

            spread = max(p90 - p10, 1e-6)
            mid = (p50 - p10) / spread
            left = int(round(mid * 20))
            bar = "█" * left + "░" * (20 - left)
            table.add_row(
                f"T+{step}",
                f"{p10:,.3f}x",
                f"{p50:,.3f}x",
                f"{p90:,.3f}x",
                f"[cyan]{bar}[/cyan]",
            )

        return Panel(table, title="[bold]Percentile Path[/bold] [dim](Monte Carlo)[/dim]", box=box.ROUNDED, border_style="magenta")
    
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

            # --- Additional Risk Metrics ---

            # Downside deviation (for Sortino)
            neg = p[p < rf_daily]
            downside_std = float(np.std(neg, ddof=1)) if len(neg) > 1 else None
            downside_vol_annual = downside_std * (252.0 ** 0.5) if downside_std else None

            sortino = None
            if downside_std and downside_std > 0:
                sortino = (avg_p - rf_daily) / downside_std * (252.0 ** 0.5)

            # Jensen's Alpha (alias of CAPM alpha)
            jensen_alpha = alpha_annual

            # Information Ratio
            excess = p - m
            te = float(np.std(excess, ddof=1))
            information_ratio = None
            if te > 0:
                information_ratio = (avg_p - avg_m) / te * (252.0 ** 0.5)

            # M-squared (Modigliani-Modigliani)
            std_m = float(np.std(m, ddof=1))
            m_squared = None
            if std_p > 0:
                m_squared = ((avg_p - rf_daily) / std_p) * std_m * 252.0 + risk_free_annual

            data = {
                "error": "",
                "beta": beta,
                "alpha_annual": alpha_annual,
                "jensen_alpha": jensen_alpha,
                "r_squared": r_squared,
                "sharpe": sharpe,
                "sortino": sortino,
                "information_ratio": information_ratio,
                "m_squared": m_squared,
                "vol_annual": vol_annual,
                "downside_vol_annual": downside_vol_annual,
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

    # toolkit.py changes

    @staticmethod
    def _compute_core_metrics(returns: pd.Series, benchmark_returns: pd.Series = None) -> dict:
        """Centralized math engine for all UI components."""
        if returns.empty:
            return {}

        # Standard Volatility (Annualized)
        vol = returns.std() * np.sqrt(252)
        
        # Sharpe (assuming 0% risk-free rate currently just for dev simplicity)
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() != 0 else 0

        metrics = {
            "volatility_annual": float(vol),
            "sharpe": float(sharpe),
            "mean_return": float(returns.mean() * 252),
        }

        if benchmark_returns is not None and not benchmark_returns.empty:
            # Align series to ensure correct covariance
            combined = pd.concat([returns, benchmark_returns], axis=1).dropna()
            if len(combined) > 5:
                cov = np.cov(combined.iloc[:, 0], combined.iloc[:, 1])[0, 1]
                mkt_var = np.var(combined.iloc[:, 1])
                beta = cov / mkt_var if mkt_var != 0 else 1.0
                metrics["beta"] = float(beta)
                
        return metrics



































class RegimeModels:
    """
    Collection of regime-based predictive models.
    """

    DEFAULT_BINS = [
        -math.inf, -0.02, -0.005, 0.005, 0.02, math.inf
    ]

    STATE_LABELS = [
        "Strong Down",
        "Mild Down",
        "Flat",
        "Mild Up",
        "Strong Up"
    ]

    INTERVAL_POINTS = {
        "1W": 5,
        "1M": 21,
        "3M": 63,
        "6M": 126,
        "1Y": 252,
    }

    @staticmethod
    def _stationary_distribution(P: list[list[float]], tol: float = 1e-12, max_iter: int = 5000) -> list[float]:
        """
        Power-iteration stationary distribution for a row-stochastic Markov chain.

        Returns pi such that pi = pi * P, sum(pi)=1.

        No clamping. No flooring. Converges for ergodic chains; otherwise returns last iterate.
        """
        n = len(P)
        if n <= 0:
            return []

        # Start uniform
        pi = [1.0 / n] * n

        it = 0
        while it < max_iter:
            # pi_next[j] = sum_i pi[i] * P[i][j]
            pi_next = [0.0] * n
            i = 0
            while i < n:
                row = P[i]
                w = float(pi[i])
                j = 0
                while j < n:
                    pi_next[j] += w * float(row[j])
                    j += 1
                i += 1

            s = float(sum(pi_next))
            if s > 0:
                inv = 1.0 / s
                j = 0
                while j < n:
                    pi_next[j] *= inv
                    j += 1

            # L1 diff
            diff = 0.0
            j = 0
            while j < n:
                diff += abs(pi_next[j] - pi[j])
                j += 1

            pi = pi_next
            if diff < tol:
                break

            it += 1

        return pi

    @staticmethod
    def _evolution_surface(P: list[list[float]], current_state: int, steps: int) -> list[list[float]]:
        """
        Returns a matrix (steps+1) x n where row t is the state probability vector at time t,
        starting from a one-hot distribution at current_state.
        """
        n = len(P)
        if n <= 0:
            return []

        # t=0
        out = []
        probs = [0.0] * n
        probs[current_state] = 1.0
        out.append(probs[:])

        t = 0
        while t < steps:
            nxt = [0.0] * n
            i = 0
            while i < n:
                pi = float(probs[i])
                if pi != 0.0:
                    row = P[i]
                    j = 0
                    while j < n:
                        nxt[j] += pi * float(row[j])
                        j += 1
                i += 1

            s = float(sum(nxt))
            if s > 0:
                inv = 1.0 / s
                j = 0
                while j < n:
                    nxt[j] *= inv
                    j += 1

            probs = nxt
            out.append(probs[:])
            t += 1

        return out

    @staticmethod
    def snapshot_from_value_series(values: list[float], interval: str = "1M", label: str = "Portfolio") -> dict:
        n = RegimeModels.INTERVAL_POINTS.get(interval, 21)
        series = values[-(n+1):] if values and len(values) >= (n+1) else values

        returns = []
        if series and len(series) >= 8:
            for i in range(1, len(series)):
                prev = float(series[i-1])
                curr = float(series[i])
                if prev > 0:
                    returns.append((curr - prev) / prev)

        snap = RegimeModels.compute_markov_snapshot(returns, horizon=1, label=f"{label} ({interval})")
        snap["interval"] = interval
        return snap

    @staticmethod
    def compute_markov_snapshot(
        returns: list[float],
        horizon: int = 1,
        label: str = "1D"
    ) -> dict:
        if not returns or len(returns) < 8:
            return {"error": "Insufficient data for regime analysis"}

        bins = RegimeModels._make_bins_quantiles(returns)
        states = RegimeModels._discretize(returns, bins)
        n = len(bins) - 1

        P = RegimeModels._transition_matrix(states, n)

        current_state = states[-1]
        probs = RegimeModels._project(P, current_state, horizon)

        next_state = max(probs, key=probs.get)

        avg_return = sum(returns) / len(returns)
        volatility = math.sqrt(
            sum((r - avg_return) ** 2 for r in returns) / len(returns)
        )

        # --- Surfaces (pure Markov; interval-compatible) ---
        pi = RegimeModels._stationary_distribution(P)
        evo_steps = 12
        evo = RegimeModels._evolution_surface(P, current_state, evo_steps)

        #
        return {
            "model": "Markov",
            "horizon": label,
            "current_regime": RegimeModels.STATE_LABELS[current_state],
            "confidence": probs[current_state],
            "state_probs": {
                RegimeModels.STATE_LABELS[i]: probs[i]
                for i in range(n)
            },
            "transition_matrix": P,
            "expected_next": {
                "regime": RegimeModels.STATE_LABELS[next_state],
                "probability": probs[next_state]
            },
            "stability": P[current_state][current_state],
            "metrics": {
                "avg_return": avg_return,
                "volatility": volatility
            },
            "stationary": {
                RegimeModels.STATE_LABELS[i]: pi[i] for i in range(n)
            },
            "evolution": {
                "steps": evo_steps,
                "series": [
                    {RegimeModels.STATE_LABELS[i]: evo[t][i] for i in range(n)}
                    for t in range(len(evo))
                ]
            },
        }

    @staticmethod
    def generate_snapshot(
        ticker: str,
        benchmark_ticker: str = "SPY",
        period: str = "1y",
        interval: str = "1d",
        risk_free_annual: float = 0.04,
    ) -> dict:
        """Generate a Markov regime snapshot using real historical returns."""
        symbol = (ticker or "").strip().upper()
        if not symbol:
            return {"error": "Missing ticker"}

        try:
            df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        except Exception as exc:
            return {"error": f"Failed to fetch data: {exc}"}

        if df is None or df.empty or "Close" not in df.columns:
            return {"error": "No historical data available"}

        returns = df["Close"].pct_change().dropna()
        if returns.empty or len(returns) < 8:
            return {"error": "Insufficient data for regime analysis"}

        snap = RegimeModels.compute_markov_snapshot(returns.tolist(), horizon=1, label=f"{symbol} ({period})")
        if "error" in snap:
            return snap

        bench_returns = pd.Series(dtype=float)
        if benchmark_ticker:
            try:
                bench = yf.download(
                    str(benchmark_ticker).upper(),
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=True,
                )
                if bench is not None and not bench.empty and "Close" in bench.columns:
                    bench_returns = bench["Close"].pct_change().dropna()
            except Exception:
                bench_returns = pd.Series(dtype=float)

        metrics = FinancialToolkit._compute_core_metrics(returns, bench_returns)

        if not bench_returns.empty and "beta" in metrics:
            combined = pd.concat([returns, bench_returns], axis=1).dropna()
            if len(combined) > 5:
                avg_p = float(combined.iloc[:, 0].mean() * 252)
                avg_m = float(combined.iloc[:, 1].mean() * 252)
                beta = float(metrics.get("beta", 0.0))
                alpha_annual = avg_p - (risk_free_annual + beta * (avg_m - risk_free_annual))
                corr = combined.iloc[:, 0].corr(combined.iloc[:, 1])
                if corr is not None:
                    metrics["r_squared"] = float(corr * corr)
                metrics["alpha_annual"] = float(alpha_annual)

        snap["metrics"].update(metrics)
        snap["ticker"] = symbol
        snap["benchmark"] = str(benchmark_ticker).upper() if benchmark_ticker else None
        return snap
    
    @staticmethod
    def _bin_returns_sigma(returns: pd.Series) -> pd.Series:
        """Bins returns using Standard Deviation thresholds for stability."""
        mu = returns.mean()
        std = returns.std()
        
        # Thresholds: +/- 1.0 sigma for Mild, +/- 2.0 sigma for Strong
        bins = [-np.inf, mu - 2*std, mu - std, mu + std, mu + 2*std, np.inf]
        labels = ["Strong Down", "Mild Down", "Neutral", "Mild Up", "Strong Up"]
        
        return pd.cut(returns, bins=bins, labels=labels)

    @staticmethod
    def _discretize(returns, bins):
        out = []
        for r in returns:
            for i in range(len(bins) - 1):
                if bins[i] <= r < bins[i + 1]:
                    out.append(i)
                    break
        return out

    @staticmethod
    def _transition_matrix(states: list[int], n: int, k: float = 0.75, self_floor: float = 0.0):
        """
        Dirichlet-smoothed transition matrix.

        k: smoothing strength (higher = more smoothing)
        self_floor: minimum probability of staying in the same regime
                (prevents unrealistically jumpy chains in sparse data)
        """
        counts = [[0.0] * n for _ in range(n)]
        for a, b in zip(states[:-1], states[1:]):
            counts[a][b] += 1.0

        P = []
        for i in range(n):
            row = counts[i]
            total = sum(row)

            # Dirichlet prior: start with uniform pseudo-counts
            smoothed = [(c + k) for c in row]
            sm_total = sum(smoothed)
            probs = [v / sm_total for v in smoothed]

            P.append(probs)

        return P

    @staticmethod
    def _make_bins_quantiles(returns: list[float]) -> list[float]:
        """
        Build 5-state bins from return quantiles so states are populated.
        Produces 6 edges: [-inf, q20, q40, q60, q80, +inf]
        """
        r = [float(x) for x in returns if x is not None]
        if len(r) < 20:
            # fallback if too few points
            return [-math.inf, -0.02, -0.005, 0.005, 0.02, math.inf]

        qs = np.quantile(r, [0.20, 0.40, 0.60, 0.80]).tolist()

        # guard against identical quantiles (flat series)
        # if too many duplicates, revert to static bins
        if len(set(round(q, 10) for q in qs)) < 3:
            return [-math.inf, -0.02, -0.005, 0.005, 0.02, math.inf]

        return [-math.inf, qs[0], qs[1], qs[2], qs[3], math.inf]

    @staticmethod
    def _project(P, current, steps):
        probs = {i: 0.0 for i in range(len(P))}
        probs[current] = 1.0

        for _ in range(steps):
            next_probs = defaultdict(float)
            for i, p in probs.items():
                for j, w in enumerate(P[i]):
                    next_probs[j] += p * w
            probs = next_probs

        return probs





































from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich import box

from utils.charts import ChartRenderer

class RegimeRenderer:
    """
    Renders RegimeSnapshot structures using Rich.
    """

    @staticmethod
    def render(snapshot: dict) -> Panel:
        if "error" in snapshot:
            return Panel(
                Text(snapshot["error"], style="bold yellow"),
                title="[bold]Market Regime[/bold]",
                border_style="yellow"
            )

        # --- LEFT: summary ---
        left = Table.grid(padding=(0, 2))
        left.add_column(style="dim")
        left.add_column(justify="right", style="bold white")

        left.add_row()
        left.add_row(
            "State",
            ChartRenderer.regime_strip(snapshot["current_regime"], width=10)
        )
        left.add_row("Model", snapshot["model"])
        left.add_row("Horizon", snapshot["horizon"])
        left.add_row("Current Regime", snapshot["current_regime"])
        left.add_row("Confidence", f"{snapshot['confidence']*100:.1f}%")
        left.add_row("Stability", f"{snapshot['stability']*100:.1f}%")
        left.add_row(
            "Avg Return",
            f"{snapshot['metrics']['avg_return']*100:.2f}%"
        )
        left.add_row(
            "Volatility",
            f"{snapshot['metrics']['volatility']*100:.2f}%"
        )

        # --- RIGHT: regime probabilities ---
        prob_table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style="bold",
            expand=False,
            width=50
        )

        prob_table.add_column("Regime")
        prob_table.add_column("Prob", justify="right")
        prob_table.add_column("")

        for name, p in snapshot["state_probs"].items():
            bar = ChartRenderer.generate_bar(p, width=18)
            color = "green" if "Up" in name else "red" if "Down" in name else "yellow"
            prob_table.add_row(
                name,
                f"{p*100:.1f}%",
                f"[{color}]{bar}[/{color}]"
            )

        layout = Table.grid(expand=True)
        layout.add_column(ratio=2)
        layout.add_column(ratio=3)

        layout.add_row(
            Panel(left, box=box.ROUNDED, title="[bold]Regime Summary[/bold]"),
            Panel(prob_table, box=box.ROUNDED, title="[bold]Regime Probabilities[/bold]")
        )

        labels = list(snapshot["state_probs"].keys())
        matrix = RegimeRenderer._render_transition_heatmap(
            snapshot["transition_matrix"],
            labels
        )
        trans_surf = RegimeRenderer._render_transition_surface(snapshot["transition_matrix"])

        matrix_grid = Table.grid(expand=True)
        matrix_grid.add_column(ratio=1)
        matrix_grid.add_column(ratio=1)

        matrix_grid.add_row(
            Panel(matrix, title="[bold]Transition Matrix[/bold]", box=box.ROUNDED),
            Panel(trans_surf, title="[bold]Transition Surface[/bold]", box=box.ROUNDED),
        )

        matrix_panel = Panel(
            matrix_grid,
            title="[bold]Transition Views[/bold] [dim](Matrix • Surface)[/dim]",
            box=box.ROUNDED
        )

        # --- Surfaces ---
        surfaces_group = None
        if snapshot.get("stationary") and snapshot.get("evolution"):
            stat_surf = RegimeRenderer._render_stationary_surface(snapshot["stationary"])
            evo_surf = RegimeRenderer._render_evolution_surface(snapshot["evolution"], labels)

            surfaces_group = Group(
                Panel(stat_surf, title="[bold]Stationary (π)[/bold]", box=box.ROUNDED),
                Panel(evo_surf, title="[bold]Evolution Surface[/bold]", box=box.ROUNDED),
            )

        # --- Matrix (full width) ---
        stack = []
        stack.append(matrix_panel)

        # --- Surfaces (full width below matrix) ---
        if surfaces_group is not None:
            stack.append(
                Panel(
                    surfaces_group,
                    title="[bold]Surfaces[/bold]",
                    box=box.ROUNDED
                )
            )
        else:
            stack.append(
                Panel(
                    "[dim]Surface data not available.[/dim]",
                    title="[bold]Surfaces[/bold]",
                    box=box.ROUNDED
                )
            )

        final = Group(
            layout,
            *stack
        )

        scope = snapshot.get("scope_label")
        interval = snapshot.get("interval")
        scope_suffix = ""
        if scope and interval:
            scope_suffix = f" [dim]({scope} • {interval})[/dim]"
        elif scope:
            scope_suffix = f" [dim]({scope})[/dim]"
        elif interval:
            scope_suffix = f" [dim]({interval})[/dim]"

        return Panel(
            final,
            title=f"[bold gold1]Regime Projection[/bold gold1]{scope_suffix}",
            border_style="yellow",
            box=box.HEAVY
        )

    @staticmethod
    def _render_transition_heatmap(P: list[list[float]], labels: list[str]) -> Table:
        heat = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", pad_edge=False)
        heat.add_column("FROM \\ TO", no_wrap=True, style="dim")
        for lab in labels:
            heat.add_column(str(lab)[:7], justify="center", no_wrap=True, width=8)

        def cell(p: Any) -> Text:
            try:
                p = float(p or 0.0)
            except (ValueError, TypeError):
                p = 0.0

            ch, col = RegimeRenderer._transition_cell_style(p)

            blocks = f"[{col}]{ch * 6}[/{col}]"
            return Text.from_markup(f"{blocks}\n[white bold]{p*100:4.1f}%[/white bold]")

        for i, row in enumerate(P):
            row_label = labels[i] if i < len(labels) else "???"
            r = [row_label]
            for p in row:
                r.append(cell(p))
            heat.add_row(*r)
        return heat

    @staticmethod
    def _render_transition_surface(P: list[list[float]]) -> Table:
        """
        Pseudo-3D surface using stacked blocks. This is a heightmap-like display suitable for terminals.
        """
        n = len(P)
        surf = Table(
            box=box.SIMPLE,
            show_header=False,
            pad_edge=False,
            expand=True,
            padding=(0, 0),
        )
        surf.add_column("Surface", no_wrap=True)

        # Render each row as a "ridge" of stacked blocks.
        # Height is proportional to probability (0..1) mapped to 0..8 blocks.
        def stack(p: float) -> str:
            levels = "▁▂▃▄▅▆▇█"
            idx = int(round(max(0.0, min(1.0, float(p))) * (len(levels) - 1)))
            return levels[idx] * 6

        i = 0
        lines = []
        while i < n:
            row = P[i]
            j = 0
            parts = []
            while j < n:
                p = float(row[j] or 0.0)
                block = stack(p)
                _, color = RegimeRenderer._transition_cell_style(p)
                parts.append(f"[{color}]{block}[/{color}]".ljust(8))
                j += 1
            lines.append(" ".join(parts))
            i += 1

        # Fit into a single column (table rows)
        for ln in lines:
            surf.add_row(Text.from_markup(ln))

        return surf

    @staticmethod
    def _render_stationary_surface(stationary: dict) -> Table:
        """
        Stationary distribution as labeled bars.
        """
        tab = Table(box=box.SIMPLE, show_header=True, header_style="bold", pad_edge=False)
        tab.add_column("Regime", no_wrap=True)
        tab.add_column("π", justify="right", width=7)
        tab.add_column("", no_wrap=True)

        for name, p in stationary.items():
            p = float(p or 0.0)
            bar = ChartRenderer.generate_bar(p, width=18)
            color = "green" if "Up" in name else "red" if "Down" in name else "yellow"
            tab.add_row(name, f"{p*100:.1f}%", f"[{color}]{bar}[/{color}]")

        return tab

    @staticmethod
    def _render_evolution_surface(evolution: dict, labels: list[str]) -> Table:
        series = evolution.get("series", []) if isinstance(evolution, dict) else []
        heat = Table(box=box.SIMPLE, show_header=True, header_style="bold white", pad_edge=False)

        heat.add_column("t (step)", justify="right", width=8, style="dim")
        for lab in labels:
            heat.add_column(str(lab)[:7], justify="center", no_wrap=True, width=9)

        def cell(p: Any) -> Text:
            # 1. Safe float conversion to prevent "Error 0"
            try:
                p_val = float(p or 0.0)
            except (ValueError, TypeError):
                p_val = 0.0

            # 2. Detailed Gradient Logic
            if p_val >= 0.90:   ch, col = "█", "bold red"
            elif p_val >= 0.70: ch, col = "█", "red"
            elif p_val >= 0.50: ch, col = "▓", "yellow"
            elif p_val >= 0.40: ch, col = "▒", "green"
            elif p_val >= 0.20: ch, col = "░", "blue"
            elif p_val >= 0.10: ch, col = "░", "cyan"
            else:               ch, col = "·", "white"

            # 3. Assemble: Multiplied blocks on top, percentage on bottom
            blocks = f"[{col}]{ch * 6}[/{col}]"
            pct = f"[white bold]{p_val*100:4.1f}%[/white bold]"
            
            return Text.from_markup(f"{blocks}\n{pct}")

        # 4. Render each time step
        for t_idx, probs in enumerate(series):
            row_label = f"T-{len(series)-t_idx-1}"
            row_data = [row_label]
            
            for i in range(len(labels)):
                current_label = labels[i]
                # Handle data whether it is a list of floats or a list of dicts
                if isinstance(probs, dict):
                    p_val = probs.get(current_label, 0.0)
                elif isinstance(probs, (list, tuple)):
                    p_val = probs[i] if i < len(probs) else 0.0
                else:
                    p_val = 0.0
                    
                row_data.append(cell(p_val))
                
            heat.add_row(*row_data)

        return heat

    @staticmethod
    def _transition_cell_style(p: float) -> tuple[str, str]:
        if p >= 0.95:
            return "█", "bold red"
        if p >= 0.85:
            return "▇", "red"
        if p >= 0.70:
            return "▆", "yellow"
        if p >= 0.55:
            return "▅", "green"
        if p >= 0.40:
            return "▄", "cyan"
        if p >= 0.25:
            return "▃", "blue"
        if p >= 0.10:
            return "▂", "dim cyan"
        return "▁", "dim white"
