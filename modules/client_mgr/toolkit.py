import math
import numpy as np
import pandas as pd
import yfinance as yf
import time
import io
import warnings
import contextlib
import logging
import os
import json
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
from interfaces.shell import ShellRenderer
from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.valuation import ValuationEngine
from utils.report_synth import ReportSynthesizer, build_report_context, build_ai_sections

# Cache for CAPM computations to avoid redundant API calls
_CAPM_CACHE = {}  # key -> {"ts": int, "data": dict}
_CAPM_TTL_SECONDS = 900  # 15 minutes

# Metric glossary for Tools output (plain-language context).
_METRIC_GLOSSARY = {
    "mean_annual": {
        "label": "Annual Return (mu)",
        "definition": "Average return per year based on the observed period, annualized.",
        "high_low": "Higher is better if positive; negative implies losses over the window.",
        "range": "Varies by asset class; compare to a benchmark.",
        "units": "Percent per year.",
        "limits": "Sensitive to outliers and sample length; past mean may not persist.",
    },
    "vol_annual": {
        "label": "Volatility (sigma)",
        "definition": "Annualized standard deviation of returns.",
        "high_low": "Higher means larger swings; lower means smoother returns.",
        "range": "Equities often 10-40% annualized.",
        "units": "Percent per year.",
        "limits": "Assumes symmetric risk; does not capture tail risk well.",
    },
    "sharpe": {
        "label": "Sharpe Ratio",
        "definition": "Excess return per unit of total volatility.",
        "high_low": "Higher is better; below 0 means underperforming risk-free rate.",
        "range": "0-1 typical, >1 strong, >2 exceptional (context matters).",
        "units": "Ratio.",
        "limits": "Assumes normal returns; very window-dependent.",
    },
    "sortino": {
        "label": "Sortino Ratio",
        "definition": "Excess return per unit of downside volatility.",
        "high_low": "Higher is better; focuses on negative moves only.",
        "range": "Compare within strategy; not directly comparable across assets.",
        "units": "Ratio.",
        "limits": "Depends on downside threshold and sample size.",
    },
    "beta": {
        "label": "Beta",
        "definition": "Sensitivity to benchmark moves (systematic risk).",
        "high_low": ">1 amplifies benchmark moves; <1 is defensive; <0 moves opposite.",
        "range": "0-2 common; can be negative for hedges.",
        "units": "Ratio.",
        "limits": "Unstable with short histories or regime shifts.",
    },
    "alpha_annual": {
        "label": "Alpha (Annual)",
        "definition": "Annualized excess return vs CAPM expectation.",
        "high_low": "Positive suggests outperformance after adjusting for beta.",
        "range": "Depends on strategy; compare to peers.",
        "units": "Percent per year.",
        "limits": "Noisy; sensitive to beta, benchmark, and risk-free rate.",
    },
    "r_squared": {
        "label": "R-Squared",
        "definition": "Fraction of return variance explained by the benchmark.",
        "high_low": "Higher means benchmark explains returns; low means more idiosyncratic.",
        "range": "0 to 1.",
        "units": "Ratio.",
        "limits": "High R-squared does not imply good performance.",
    },
    "tracking_error": {
        "label": "Tracking Error",
        "definition": "Volatility of excess returns vs the benchmark.",
        "high_low": "Higher means more active deviation from benchmark.",
        "range": "Often 1-8% for active strategies.",
        "units": "Percent per year.",
        "limits": "Does not show direction; can be high for intentional tilts.",
    },
    "information_ratio": {
        "label": "Information Ratio",
        "definition": "Excess return per unit of tracking error.",
        "high_low": "Higher is better; negative means underperforming benchmark.",
        "range": "0-0.5 modest, >0.5 strong (context matters).",
        "units": "Ratio.",
        "limits": "Sensitive to window length and benchmark choice.",
    },
    "treynor": {
        "label": "Treynor Ratio",
        "definition": "Excess return per unit of beta (systematic risk).",
        "high_low": "Higher is better for market risk taken.",
        "range": "Compare within similar benchmark exposure.",
        "units": "Percent per beta.",
        "limits": "Assumes beta is stable and meaningful.",
    },
    "m_squared": {
        "label": "M-squared",
        "definition": "Risk-adjusted return scaled to benchmark volatility.",
        "high_low": "Positive means outperformed at benchmark risk level.",
        "range": "Compare to benchmark return.",
        "units": "Percent per year.",
        "limits": "Assumes benchmark is appropriate and volatility is stable.",
    },
    "max_drawdown": {
        "label": "Max Drawdown",
        "definition": "Worst peak-to-trough decline in the period.",
        "high_low": "More negative is worse; close to 0 is better.",
        "range": "-100% to 0%.",
        "units": "Percent.",
        "limits": "Single worst event; highly window-dependent.",
    },
    "var_95": {
        "label": "VaR 95%",
        "definition": "Historical loss threshold not exceeded 95% of the time.",
        "high_low": "More negative means larger potential loss.",
        "range": "Depends on asset and horizon.",
        "units": "Percent per period.",
        "limits": "Assumes future resembles past; ignores tail losses beyond VaR.",
    },
    "cvar_95": {
        "label": "CVaR 95%",
        "definition": "Average loss in the worst 5% of periods.",
        "high_low": "More negative is worse; captures tail severity.",
        "range": "Depends on asset and horizon.",
        "units": "Percent per period.",
        "limits": "Requires enough tail data; unstable with short samples.",
    },
    "var_99": {
        "label": "VaR 99%",
        "definition": "Historical loss threshold not exceeded 99% of the time.",
        "high_low": "More negative means larger potential loss.",
        "range": "Depends on asset and horizon.",
        "units": "Percent per period.",
        "limits": "Sparse tail data; sensitive to outliers.",
    },
    "cvar_99": {
        "label": "CVaR 99%",
        "definition": "Average loss in the worst 1% of periods.",
        "high_low": "More negative is worse; focuses on extreme tail risk.",
        "range": "Depends on asset and horizon.",
        "units": "Percent per period.",
        "limits": "Very unstable with limited history.",
    },
    "entropy": {
        "label": "Entropy",
        "definition": "Shannon entropy of the return distribution (bin-based).",
        "high_low": "Higher implies more uniform return outcomes; lower implies concentrated outcomes.",
        "range": "Depends on binning; compare within the same setup.",
        "units": "Bits (relative).",
        "limits": "Sensitive to bin choices and sample size; this is not permutation entropy.",
    },
    "perm_entropy": {
        "label": "Permutation Entropy",
        "definition": "Entropy of ordinal return patterns (order m, delay tau).",
        "high_low": "Higher implies more complex or irregular time-order patterns.",
        "range": "Normalized 0 to 1 for the chosen order.",
        "units": "Ratio (0-1).",
        "limits": "Sensitive to order and delay; short series can understate complexity. Configure in Settings -> Tools.",
    },
    "hurst": {
        "label": "Hurst Exponent",
        "definition": "Trend persistence measure from price path.",
        "high_low": ">0.5 suggests trend persistence; <0.5 suggests mean reversion.",
        "range": "Typically 0 to 1.",
        "units": "Ratio.",
        "limits": "Requires enough data; non-stationary series can mislead.",
    },
    "skew": {
        "label": "Skewness",
        "definition": "Asymmetry of returns around the mean.",
        "high_low": "Positive skew implies more right-tail wins; negative implies downside tail.",
        "range": "Often between -1 and 1 for liquid assets.",
        "units": "Ratio.",
        "limits": "Very noisy with small samples.",
    },
    "kurtosis": {
        "label": "Kurtosis",
        "definition": "Tail heaviness relative to normal distribution.",
        "high_low": "Higher than 3 implies fatter tails.",
        "range": "3 is normal; >3 heavy tails.",
        "units": "Ratio.",
        "limits": "Highly sensitive to outliers.",
    },
    "autocorr_lag1": {
        "label": "Autocorr (Lag 1)",
        "definition": "Correlation between returns and prior period returns.",
        "high_low": "Positive suggests momentum; negative suggests mean reversion.",
        "range": "-1 to 1.",
        "units": "Correlation.",
        "limits": "Unstable with short histories; can flip by regime.",
    },
    "downside_vol_annual": {
        "label": "Downside Volatility",
        "definition": "Annualized volatility of returns below the threshold.",
        "high_low": "Higher means more downside variability.",
        "range": "Varies; compare to total volatility.",
        "units": "Percent per year.",
        "limits": "Depends on chosen threshold and sample length.",
    },
}

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
            recommendations.append(f"[red]AGGRESSIVE WARN[/red]: Check Sortino Ratio (Downside volatility focus for high risk assets)\n  - see Multi-Model Risk Dashboard")
        
        recommendations.append("CAPM (Capital Asset Pricing Model) - Standard Equity Baseline")
        
        return recommendations






































class FinancialToolkit:
    """
    Advanced financial analysis tools context-aware of a specific client's portfolio.
    """
    PERM_ENTROPY_ORDER = 3
    PERM_ENTROPY_DELAY = 1

    def __init__(self, client: Client):
        self.client = client
        self.console = Console()
        self.valuation = ValuationEngine()
        self.benchmark_ticker = "SPY" # Using S&P 500 ETF as standard benchmark
        self._pattern_cache = {}
        self._settings_file = os.path.join(os.getcwd(), "config", "settings.json")
        tool_settings = self._load_tool_settings()
        self.perm_entropy_order = tool_settings["perm_entropy_order"]
        self.perm_entropy_delay = tool_settings["perm_entropy_delay"]
        interval = str(self.client.active_interval or "1M").upper()
        self._selected_interval = interval if interval in TOOLKIT_PERIOD else "1M"

    def _load_ai_settings(self) -> dict:
        defaults = {
            "enabled": True,
            "provider": "auto",
            "model_id": "rule_based_v1",
            "persona": "advisor_legal_v1",
            "cache_ttl": 21600,
            "cache_file": "data/ai_report_cache.json",
            "endpoint": "",
        }
        if not os.path.exists(self._settings_file):
            return defaults
        try:
            with open(self._settings_file, "r", encoding="ascii") as f:
                data = json.load(f)
            ai_conf = data.get("ai", {}) if isinstance(data, dict) else {}
        except Exception:
            return defaults
        if not isinstance(ai_conf, dict):
            ai_conf = {}
        for key, value in defaults.items():
            if key not in ai_conf:
                ai_conf[key] = value
        return ai_conf

    def _load_tool_settings(self) -> dict:
        defaults = {
            "perm_entropy_order": self.PERM_ENTROPY_ORDER,
            "perm_entropy_delay": self.PERM_ENTROPY_DELAY,
        }
        if not os.path.exists(self._settings_file):
            return defaults
        try:
            with open(self._settings_file, "r", encoding="ascii") as f:
                data = json.load(f)
            tools_conf = data.get("tools", {}) if isinstance(data, dict) else {}
        except Exception:
            return defaults
        if not isinstance(tools_conf, dict):
            tools_conf = {}
        order = tools_conf.get("perm_entropy_order", defaults["perm_entropy_order"])
        delay = tools_conf.get("perm_entropy_delay", defaults["perm_entropy_delay"])
        try:
            order = int(order)
        except Exception:
            order = defaults["perm_entropy_order"]
        try:
            delay = int(delay)
        except Exception:
            delay = defaults["perm_entropy_delay"]
        if order < 2:
            order = defaults["perm_entropy_order"]
        if delay < 1:
            delay = defaults["perm_entropy_delay"]
        return {
            "perm_entropy_order": order,
            "perm_entropy_delay": delay,
        }

    def _render_ai_sections(self, sections: list) -> Optional[Group]:
        if not sections:
            return None
        panels = []
        for section in sections:
            title = str(section.get("title", "Advisor Notes"))
            rows = section.get("rows", []) or []
            if rows and isinstance(rows[0], list):
                table = Table.grid(padding=(0, 1))
                table.add_column(style="bold cyan", width=18)
                table.add_column(style="white")
                for row in rows:
                    left = str(row[0]) if len(row) > 0 else ""
                    right = str(row[1]) if len(row) > 1 else ""
                    table.add_row(left, right)
                body = table
            else:
                text = Text()
                for row in rows:
                    text.append(f"{row}\n")
                body = text
            panels.append(Panel(body, title=title, border_style="cyan"))
        return Group(*panels)

    def _build_ai_panel(self, report: dict, report_type: str) -> Optional[Group]:
        ai_conf = self._load_ai_settings()
        if not bool(ai_conf.get("enabled", True)):
            return None
        synthesizer = ReportSynthesizer(
            provider=str(ai_conf.get("provider", "rule_based")),
            model_id=str(ai_conf.get("model_id", "rule_based_v1")),
            persona=str(ai_conf.get("persona", "advisor_legal_v1")),
            cache_file=str(ai_conf.get("cache_file", "data/ai_report_cache.json")),
            cache_ttl=int(ai_conf.get("cache_ttl", 21600)),
            endpoint=str(ai_conf.get("endpoint", "")),
        )
        context = build_report_context(
            report,
            report_type,
            region="Global",
            industry="portfolio",
            news_items=[],
        )
        ai_payload = synthesizer.synthesize(context)
        sections = build_ai_sections(ai_payload)
        return self._render_ai_sections(sections)

    def _prompt_menu(
        self,
        title: str,
        options: Dict[str, str],
        show_main: bool = True,
        show_back: bool = True,
        show_exit: bool = True,
    ) -> str:
        table = Table.grid(padding=(0, 1))
        table.add_column()
        for key, label in options.items():
            table.add_row(f"[bold cyan]{key}[/bold cyan]  {label}")
        panel = Panel(table, title=title, border_style="cyan", box=box.ROUNDED)
        return ShellRenderer.render_and_prompt(
            Group(panel),
            context_actions=options,
            valid_choices=list(options.keys()) + ["m", "x"],
            prompt_label=">",
            show_main=show_main,
            show_back=show_back,
            show_exit=show_exit,
            show_header=False,
        )

    def run(self):
        """Main loop for the Client Tools module."""
        while True:
            self.console.clear()
            print("\x1b[3J", end="")
            self.console.print(f"[bold gold1]TOOLS | {self.client.name}[/bold gold1]")
            
            # --- AUTO MODEL SELECTION ---
            recs = ModelSelector.analyze_suitability(self.client)
            if recs:
                self.console.print(Panel(
                    "\n".join([f"• {r}" for r in recs]),
                    title="[bold green]Recommended Models[/bold green]",
                    border_style="green",
                    width=100
                ))
            
            self.console.print("\n[bold white]Quantitative Models[/bold white]")
            self.console.print("[1] CAPM Analysis (Alpha, Beta, R²)")
            self.console.print("[2] Black-Scholes Option Pricing")
            self.console.print("[3] Multi-Model Risk Dashboard")
            self.console.print("[4] Portfolio Regime Snapshot")
            self.console.print("[5] Portfolio Diagnostics")
            self.console.print("[6] Pattern Analysis")
            self.console.print(f"[7] Change Interval (Current: {self._selected_interval})")
            self.console.print("[0] Return to Client Dashboard")
            
            choice = self._prompt_menu(
                "Tools Menu",
                {
                    "1": "CAPM Analysis (Alpha, Beta, R-squared)",
                    "2": "Black-Scholes Option Pricing",
                    "3": "Multi-Model Risk Dashboard",
                    "4": "Portfolio Regime Snapshot",
                    "5": "Portfolio Diagnostics",
                    "6": "Pattern Analysis",
                    "7": f"Change Interval (Current: {self._selected_interval})",
                    "0": "Return to Client Dashboard",
                },
            )

            if choice == "0":
                break
            if choice == "m":
                break
            if choice == "x":
                return
            elif choice == "1":
                self._run_capm_analysis()
            elif choice == "2":
                self._run_black_scholes()
            elif choice == "3":
                self._run_multi_model_dashboard()
            elif choice == "4":
                self._run_regime_snapshot()
            elif choice == "5":
                self._run_portfolio_diagnostics()
            elif choice == "6":
                self._run_pattern_suite()
            elif choice == "7":
                updated = self._get_interval_or_select(force=True)
                if updated:
                    self._selected_interval = updated

    # --- REAL-TIME DATA ANALYSIS TOOLS ---

    def _run_capm_analysis(self):
        """
        Calculates CAPM and risk metrics using shared toolkit functions.
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

        self.console.print("\nFetching shared CAPM metrics...")
        ShellRenderer.set_busy(1.0)
        capm = FinancialToolkit.compute_capm_metrics_from_holdings(
            consolidated_holdings,
            benchmark_ticker=self.benchmark_ticker,
            period="1y",
        )
        if capm.get("error"):
            self.console.print(f"[yellow]{capm.get('error')}[/yellow]")
            InputSafe.pause()
            return

        results = Table(title="CAPM Metrics (1 Year Lookback)", box=box.ROUNDED)
        results.add_column("Metric", style="bold white")
        results.add_column("Value", justify="right", style="bold cyan")
        results.add_column("Interpretation", style="italic dim")
        
        beta = capm.get("beta")
        alpha_annualized = capm.get("alpha_annual")
        r_squared = capm.get("r_squared")
        sharpe = capm.get("sharpe")
        vol_annual = capm.get("vol_annual")

        results.add_row("Beta", f"{beta:.2f}" if beta is not None else "N/A", "Volatility relative to S&P 500")
        results.add_row("Alpha (Annual)", f"{alpha_annualized:.2%}" if alpha_annualized is not None else "N/A", "Excess return vs. risk taken")
        results.add_row("R-Squared", f"{r_squared:.2f}" if r_squared is not None else "N/A", "Correlation to benchmark")
        results.add_row(
            "Sharpe",
            f"{sharpe:.2f}" if sharpe is not None else "N/A",
            "Risk-adjusted return"
        )
        results.add_row(
            "Volatility (Ann.)",
            f"{vol_annual:.2%}" if vol_annual is not None else "N/A",
            "Annualized standard deviation"
        )

        self.console.print(Align.center(results))
        self.console.print(
            self._render_metric_glossary(
                ["beta", "alpha_annual", "r_squared", "sharpe", "vol_annual"],
                title="CAPM Metric Context",
            )
        )

        risk_level = "Moderate"
        if beta is not None and beta > 1.2:
            risk_level = "High"
        elif beta is not None and beta < 0.8:
            risk_level = "Low"
        signals = []
        if beta is not None:
            signals.append(f"Beta {beta:.2f}")
        if sharpe is not None:
            signals.append(f"Sharpe {sharpe:.2f}")
        if vol_annual is not None:
            signals.append(f"Volatility {vol_annual:.2%}")
        if alpha_annualized is not None:
            signals.append(f"Alpha {alpha_annualized:+.2%}")
        impacts = []
        if beta is not None and beta > 1.2:
            impacts.append("Market sensitivity elevated.")
        elif beta is not None and beta < 0.8:
            impacts.append("Defensive tilt vs benchmark.")
        if sharpe is not None and sharpe < 0.5:
            impacts.append("Risk-adjusted returns below target.")
        report = {
            "summary": [
                f"Benchmark: {self.benchmark_ticker}",
                f"Holdings: {len(consolidated_holdings)}",
            ],
            "risk_level": risk_level,
            "risk_score": None,
            "confidence": "Medium" if signals else "Low",
            "signals": signals,
            "impacts": impacts,
            "sections": [
                {
                    "title": "CAPM Overview",
                    "rows": [
                        ["Beta", f"{beta:.2f}" if beta is not None else "N/A"],
                        ["Alpha (Annual)", f"{alpha_annualized:.2%}" if alpha_annualized is not None else "N/A"],
                        ["R-Squared", f"{r_squared:.2f}" if r_squared is not None else "N/A"],
                        ["Sharpe", f"{sharpe:.2f}" if sharpe is not None else "N/A"],
                        ["Volatility", f"{vol_annual:.2%}" if vol_annual is not None else "N/A"],
                    ],
                }
            ],
        }
        ai_panel = self._build_ai_panel(report, "capm_analysis")
        if ai_panel:
            self.console.print(ai_panel)
        self.console.print(self._render_capm_context(capm))

        # Interpretation Logic
        if beta and beta > 1.2:
            self.console.print("\n[bold yellow]⚠ High Volatility:[/bold yellow] This client portfolio is significantly more volatile than the market.")
        elif beta and beta < 0.8:
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

        call_price, put_price = self._black_scholes_price(
            spot_price,
            strike_price,
            time_years,
            volatility,
            risk_free,
        )

        def format_price(value: float) -> str:
            if value is None or not math.isfinite(value):
                return "N/A"
            return f"${value:.4f}"

        # --- OUTPUT ---
        results = Table(title=f"Option Chain Valuation: {ticker if ticker else 'CUSTOM'}", box=box.ROUNDED)
        results.add_column("Metric", style="dim")
        results.add_column("Value", style="bold white")

        results.add_row("Underlying Price", f"${spot_price:.2f}")
        results.add_row("Strike Price", f"${strike_price:.2f}")
        results.add_row("Time (Years)", f"{time_years:.4f}")
        results.add_section()
        results.add_row("[bold green]CALL Value[/bold green]", f"[bold green]{format_price(call_price)}[/bold green]")
        results.add_row("[bold red]PUT Value[/bold red]", f"[bold red]{format_price(put_price)}[/bold red]")

        self.console.print("\n")
        self.console.print(Align.center(results))
        self.console.print(self._render_black_scholes_context(spot_price, strike_price, time_years, volatility, risk_free))
        InputSafe.pause()

    @staticmethod
    def _black_scholes_price(
        spot_price: float,
        strike_price: float,
        time_years: float,
        volatility: float,
        risk_free: float,
    ) -> Tuple[float, float]:
        if spot_price <= 0 or strike_price <= 0 or time_years <= 0 or volatility <= 0:
            return float("nan"), float("nan")

        d1 = (math.log(spot_price / strike_price) + (risk_free + 0.5 * volatility ** 2) * time_years) / (volatility * math.sqrt(time_years))
        d2 = d1 - volatility * math.sqrt(time_years)

        def N(x: float) -> float:
            return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

        call_price = spot_price * N(d1) - strike_price * math.exp(-risk_free * time_years) * N(d2)
        put_price = strike_price * math.exp(-risk_free * time_years) * N(-d2) - spot_price * N(-d1)
        return float(call_price), float(put_price)

    def _run_multi_model_dashboard(self):
        """Compute a multi-model risk dashboard for the client's portfolio."""
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print(f"[bold blue]MULTI-MODEL RISK DASHBOARD[/bold blue]")

        interval = self._get_interval_or_select()
        if not interval:
            return

        holdings = self._aggregate_holdings()
        if not holdings:
            self.console.print("[yellow]No holdings available for analysis.[/yellow]")
            InputSafe.pause()
            return

        period = TOOLKIT_PERIOD.get(interval, "1y")
        ShellRenderer.set_busy(1.0)
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
        self.console.print(self._render_risk_dashboard_context(interval, meta))
        InputSafe.pause()

    def _aggregate_lots(self) -> Dict[str, List[Dict[str, Any]]]:
        lots = {}
        for acc in self.client.accounts:
            for ticker, entries in (acc.lots or {}).items():
                lots.setdefault(ticker, []).extend(entries or [])
        return lots

    def _run_regime_snapshot(self):
        """Generate a regime snapshot from portfolio value history."""
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print(f"[bold blue]PORTFOLIO REGIME SNAPSHOT[/bold blue]")

        interval = self._get_interval_or_select()
        if not interval:
            return

        holdings = self._aggregate_holdings()
        if not holdings:
            self.console.print("[yellow]No holdings available for analysis.[/yellow]")
            InputSafe.pause()
            return

        lots = self._aggregate_lots()
        period = TOOLKIT_PERIOD.get(interval, "1y")
        ShellRenderer.set_busy(1.0)
        _, enriched = self.valuation.calculate_portfolio_value(
            holdings,
            history_period=period,
            history_interval=TOOLKIT_INTERVAL.get(interval, "1d"),
        )
        _, history = self.valuation.generate_portfolio_history_series(
            enriched_data=enriched,
            holdings=holdings,
            interval=interval,
            lot_map=lots,
        )

        snap = RegimeModels.snapshot_from_value_series(history, interval=interval, label=self.client.name)
        snap["scope_label"] = "Portfolio"
        snap["interval"] = interval
        self.console.print(RegimeRenderer.render(snap))
        self.console.print(self._render_regime_context(snap))
        InputSafe.pause()

    def _run_portfolio_diagnostics(self):
        """Run a consolidated diagnostics report using shared metrics."""
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print(f"[bold blue]PORTFOLIO DIAGNOSTICS[/bold blue]")

        interval = self._get_interval_or_select()
        if not interval:
            return

        holdings = self._aggregate_holdings()
        if not holdings:
            self.console.print("[yellow]No holdings available for analysis.[/yellow]")
            InputSafe.pause()
            return

        period = TOOLKIT_PERIOD.get(interval, "1y")
        ShellRenderer.set_busy(1.0)
        returns, bench_returns, meta = self._get_portfolio_and_benchmark_returns(
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
            benchmark_returns=bench_returns,
            risk_free_annual=0.04,
        )
        ShellRenderer.set_busy(1.0)
        capm = FinancialToolkit.compute_capm_metrics_from_holdings(
            holdings,
            benchmark_ticker=self.benchmark_ticker,
            period=period,
        )
        ShellRenderer.set_busy(1.0)
        total_val, enriched = self.valuation.calculate_portfolio_value(
            holdings,
            history_period=period,
            history_interval=TOOLKIT_INTERVAL.get(interval, "1d"),
        )
        manual_total = 0.0
        for acc in self.client.accounts:
            ShellRenderer.set_busy(0.4)
            m_val, _ = self.valuation.calculate_manual_holdings_value(acc.manual_holdings)
            manual_total += float(m_val or 0.0)

        sector_totals = defaultdict(float)
        for data in enriched.values():
            sector = str(data.get("sector", "N/A") or "N/A")
            sector_totals[sector] += float(data.get("market_value", 0.0) or 0.0)
        sector_rows = sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
        hhi = 0.0
        if total_val > 0:
            for _, val in sector_rows:
                pct = val / total_val
                hhi += pct * pct

        top_holdings = sorted(
            enriched.values(),
            key=lambda item: float(item.get("market_value", 0.0) or 0.0),
            reverse=True,
        )[:5]

        movers = []
        for data in enriched.values():
            pct = data.get("change_pct")
            if pct is None:
                continue
            movers.append({
                "ticker": data.get("ticker"),
                "pct": float(pct),
                "change": float(data.get("change", 0.0) or 0.0),
                "value": float(data.get("market_value", 0.0) or 0.0),
            })
        gainers = sorted(movers, key=lambda item: item["pct"], reverse=True)[:5]
        losers = sorted(movers, key=lambda item: item["pct"])[:5]

        account_rows = []
        for acc in self.client.accounts:
            acc_value = 0.0
            acc_change = 0.0
            for ticker, qty in (acc.holdings or {}).items():
                data = enriched.get(str(ticker).upper())
                if not data:
                    continue
                price = float(data.get("price", 0.0) or 0.0)
                change = float(data.get("change", 0.0) or 0.0)
                acc_value += price * float(qty or 0.0)
                acc_change += change * float(qty or 0.0)
            base = acc_value - acc_change
            acc_pct = (acc_change / base) if base > 0 else None
            account_rows.append({
                "name": acc.account_name,
                "value": acc_value,
                "change": acc_change,
                "pct": acc_pct,
                "holdings": len(acc.holdings or {}),
            })

        table = Table(box=box.ROUNDED, expand=True, title="Diagnostics Summary")
        table.add_column("Metric", style="bold white")
        table.add_column("Value", justify="right")
        table.add_column("Notes", style="dim")

        table.add_row("Interval", interval, meta)
        table.add_row("Holdings", str(len(holdings)), "Non-zero positions")
        table.add_row("Market Value", f"{total_val:,.0f}", "Tracked holdings value")
        if manual_total > 0:
            table.add_row("Manual Assets", f"{manual_total:,.0f}", "Off-market holdings")
        table.add_row("Annual Return", f"{metrics.get('mean_annual', 0.0):+.2%}", "Average annualized return")
        table.add_row("Volatility", f"{metrics.get('vol_annual', 0.0):.2%}", "Annualized std dev")
        table.add_row("Sharpe", f"{metrics.get('sharpe', 0.0):.2f}" if metrics.get("sharpe") is not None else "N/A", "Risk-adjusted")
        table.add_row("Sortino", f"{metrics.get('sortino', 0.0):.2f}" if metrics.get("sortino") is not None else "N/A", "Downside-adjusted")
        if metrics.get("max_drawdown") is not None:
            table.add_row("Max Drawdown", f"{metrics.get('max_drawdown', 0.0):.2%}", "Peak-to-trough")
        if metrics.get("var_95") is not None:
            table.add_row("VaR 95%", f"{metrics.get('var_95', 0.0):+.2%}", "Historical quantile")
        if metrics.get("cvar_95") is not None:
            table.add_row("CVaR 95%", f"{metrics.get('cvar_95', 0.0):+.2%}", "Expected tail loss")
        if capm.get("beta") is not None:
            table.add_row("Beta", f"{capm.get('beta'):.2f}", "Systemic risk")
        if capm.get("alpha_annual") is not None:
            table.add_row("Alpha", f"{capm.get('alpha_annual'):+.2%}", "Excess return")
        if capm.get("r_squared") is not None:
            table.add_row("R-Squared", f"{capm.get('r_squared'):.2f}", "Benchmark fit")

        self.console.print(table)
        self.console.print(
            self._render_metric_glossary(
                [
                    "mean_annual",
                    "vol_annual",
                    "sharpe",
                    "sortino",
                    "max_drawdown",
                    "var_95",
                    "cvar_95",
                    "beta",
                    "alpha_annual",
                    "r_squared",
                ],
                title="Diagnostics Metric Context",
            )
        )
        self.console.print(self._render_diagnostics_context(interval, total_val, manual_total, sector_rows, hhi))
        if sector_rows:
            sector_table = Table(box=box.SIMPLE, expand=True, title="Sector Concentration")
            sector_table.add_column("Sector", style="bold cyan")
            sector_table.add_column("Value", justify="right")
            sector_table.add_column("Alloc", justify="right")
            sector_table.add_column("Heat", justify="center", width=6)
            for sector, value in sector_rows[:6]:
                pct = (value / total_val) if total_val > 0 else 0.0
                heat = ChartRenderer.generate_heatmap_bar(pct, width=6)
                sector_table.add_row(sector, f"{value:,.0f}", f"{pct:.1%}", heat)
            if hhi > 0:
                sector_table.add_row("HHI", f"{hhi:.3f}", "Concentration index", "")
            self.console.print(sector_table)

        if top_holdings:
            top_table = Table(box=box.SIMPLE, expand=True, title="Top Holdings")
            top_table.add_column("Ticker", style="bold cyan")
            top_table.add_column("Value", justify="right")
            top_table.add_column("Alloc", justify="right")
            top_table.add_column("Change", justify="right")
            for data in top_holdings:
                value = float(data.get("market_value", 0.0) or 0.0)
                pct = (value / total_val) if total_val > 0 else 0.0
                change = float(data.get("change", 0.0) or 0.0)
                color = "green" if change >= 0 else "red"
                top_table.add_row(
                    str(data.get("ticker", "")),
                    f"{value:,.0f}",
                    f"{pct:.1%}",
                    f"[{color}]{change:+.2f}[/{color}]",
                )
            self.console.print(top_table)

        if movers:
            mover_table = Table(box=box.SIMPLE, expand=True, title="Top Movers (1D %)")
            mover_table.add_column("Type", style="bold")
            mover_table.add_column("Ticker", style="bold cyan")
            mover_table.add_column("Change %", justify="right")
            mover_table.add_column("Change", justify="right")
            for row in gainers:
                mover_table.add_row("Gainer", str(row["ticker"]), f"{row['pct']:+.2%}", f"{row['change']:+.2f}")
            for row in losers:
                mover_table.add_row("Loser", str(row["ticker"]), f"{row['pct']:+.2%}", f"{row['change']:+.2f}")
            self.console.print(mover_table)

        if account_rows:
            acct_table = Table(box=box.SIMPLE, expand=True, title="Account Deltas (1D)")
            acct_table.add_column("Account", style="bold cyan")
            acct_table.add_column("Value", justify="right")
            acct_table.add_column("Change", justify="right")
            acct_table.add_column("Change %", justify="right")
            acct_table.add_column("Holdings", justify="right", style="dim")
            for row in sorted(account_rows, key=lambda item: item["value"], reverse=True):
                pct = row["pct"]
                color = "green" if (row["change"] or 0.0) >= 0 else "red"
                pct_text = f"{pct:+.2%}" if pct is not None else "N/A"
                acct_table.add_row(
                    row["name"],
                    f"{row['value']:,.0f}",
                    f"[{color}]{row['change']:+.2f}[/{color}]",
                    pct_text,
                    str(row["holdings"]),
                )
            self.console.print(acct_table)

            sector_table = Table(box=box.SIMPLE, expand=True, title="Account Sector Mix")
            sector_table.add_column("Account", style="bold cyan")
            sector_table.add_column("Top Sectors", style="white")
            sector_table.add_column("HHI", justify="right", style="dim")
            sector_table.add_column("Heat", justify="center", width=6)

            for acc in sorted(self.client.accounts, key=lambda a: a.account_name):
                acc_sector_totals = defaultdict(float)
                acc_value = 0.0
                for ticker, qty in (acc.holdings or {}).items():
                    data = enriched.get(str(ticker).upper())
                    if not data:
                        continue
                    sector = str(data.get("sector", "N/A") or "N/A")
                    value = float(data.get("market_value", 0.0) or 0.0)
                    acc_sector_totals[sector] += value
                    acc_value += value

                if acc_value <= 0:
                    sector_table.add_row(acc.account_name, "N/A", "N/A", "-")
                    continue

                sector_rows = sorted(acc_sector_totals.items(), key=lambda item: item[1], reverse=True)
                top_sectors = []
                hhi_acc = 0.0
                for sector, value in sector_rows:
                    pct = value / acc_value
                    hhi_acc += pct * pct
                for sector, value in sector_rows[:3]:
                    pct = value / acc_value
                    top_sectors.append(f"{sector} {pct:.0%}")

                heat = ChartRenderer.generate_heatmap_bar(min(hhi_acc, 1.0), width=6)
                sector_table.add_row(
                    acc.account_name,
                    ", ".join(top_sectors) if top_sectors else "N/A",
                    f"{hhi_acc:.3f}",
                    heat,
                )

            self.console.print(sector_table)
        drawdown = metrics.get("max_drawdown") if isinstance(metrics, dict) else None
        vol = metrics.get("vol_annual") if isinstance(metrics, dict) else None
        sharpe = metrics.get("sharpe") if isinstance(metrics, dict) else None
        risk_level = "Moderate"
        if drawdown is not None and abs(float(drawdown)) >= 0.2:
            risk_level = "High"
        elif vol is not None and float(vol) >= 0.25:
            risk_level = "High"
        elif sharpe is not None and float(sharpe) >= 0.9:
            risk_level = "Low"

        signals = []
        if vol is not None:
            signals.append(f"Volatility {float(vol):.2%}")
        if sharpe is not None:
            signals.append(f"Sharpe {float(sharpe):.2f}")
        if drawdown is not None:
            signals.append(f"Max Drawdown {float(drawdown):.2%}")
        if capm.get("beta") is not None:
            signals.append(f"Beta {capm.get('beta'):.2f}")
        impacts = []
        if hhi > 0.2:
            impacts.append("Concentration risk elevated.")
        if sharpe is not None and float(sharpe) < 0.5:
            impacts.append("Risk-adjusted returns below target.")
        report = {
            "summary": [
                f"Interval: {interval}",
                f"Market Value: ${total_val:,.0f}",
                f"Manual Assets: ${manual_total:,.0f}",
                f"Holdings: {len(holdings)}",
            ],
            "risk_level": risk_level,
            "risk_score": None,
            "confidence": "Medium" if signals else "Low",
            "signals": signals,
            "impacts": impacts,
            "sections": [
                {
                    "title": "Diagnostics Summary",
                    "rows": [
                        ["Interval", interval],
                        ["Market Value", f"{total_val:,.0f}"],
                        ["Manual Assets", f"{manual_total:,.0f}"],
                        ["Volatility", f"{float(vol):.2%}" if vol is not None else "N/A"],
                        ["Sharpe", f"{float(sharpe):.2f}" if sharpe is not None else "N/A"],
                        ["Max Drawdown", f"{float(drawdown):.2%}" if drawdown is not None else "N/A"],
                    ],
                }
            ],
        }
        ai_panel = self._build_ai_panel(report, "portfolio_diagnostics")
        if ai_panel:
            self.console.print(ai_panel)
        InputSafe.pause()

    def _run_pattern_suite(self):
        """Pattern analysis is using existing return series."""
        while True:
            self.console.clear()
            print("\x1b[3J", end="")
            self.console.print(f"[bold blue]PATTERN ANALYSIS[/bold blue]")

            interval = self._get_interval_or_select()
            if not interval:
                return

            holdings = self._aggregate_holdings()
            if not holdings:
                self.console.print("[yellow]No holdings available for analysis.[/yellow]")
                InputSafe.pause()
                return

            period = TOOLKIT_PERIOD.get(interval, "1y")
            ShellRenderer.set_busy(1.0)
            returns, bench_returns, meta = self._get_portfolio_and_benchmark_returns(
                holdings,
                benchmark_ticker=self.benchmark_ticker,
                period=period,
                interval=TOOLKIT_INTERVAL.get(interval, "1d"),
            )
            if returns is None or returns.empty:
                self.console.print("[yellow]Insufficient market data for this interval.[/yellow]")
                InputSafe.pause()
                return

            payload = self._get_pattern_payload(returns, interval, meta)
            self.console.print(
                self._render_metric_glossary(
                    ["entropy", "perm_entropy", "hurst"],
                    title="Pattern Metric Context",
                )
            )
            self.console.print(self._render_entropy_panel(payload))
            entropy = payload.get("entropy")
            perm_entropy = payload.get("perm_entropy")
            hurst = payload.get("hurst")
            spectrum = payload.get("spectrum") or []
            change_points = payload.get("change_points") or []
            signals = []
            if spectrum:
                for freq, power in spectrum[:2]:
                    signals.append(f"Cycle freq {float(freq):.2f} (power {float(power):.2f})")
            if change_points:
                signals.append(f"Change points: {len(change_points)}")
            if entropy is not None:
                signals.append(f"Entropy {float(entropy):.2f}")
            if perm_entropy is not None:
                signals.append(f"Perm Entropy {float(perm_entropy):.2f}")
            if hurst is not None:
                signals.append(f"Hurst {float(hurst):.2f}")
            impacts = []
            if hurst is not None and float(hurst) > 0.6:
                impacts.append("Trend persistence elevated.")
            elif hurst is not None and float(hurst) < 0.4:
                impacts.append("Mean reversion signals elevated.")
            report = {
                "summary": [
                    f"Interval: {interval}",
                    f"Scope: {meta}",
                ],
                "risk_level": "Moderate",
                "risk_score": None,
                "confidence": "Medium" if signals else "Low",
                "signals": signals,
                "impacts": impacts,
                "sections": [
                    {
                        "title": "Pattern Summary",
                        "rows": [
                            ["Entropy", f"{float(entropy):.2f}" if entropy is not None else "N/A"],
                            ["Hurst", f"{float(hurst):.2f}" if hurst is not None else "N/A"],
                            ["Change Points", str(len(change_points))],
                            ["Top Cycles", ", ".join([f"{float(freq):.2f}" for freq, _ in spectrum[:3]]) or "N/A"],
                        ],
                    }
                ],
            }
            ai_panel = self._build_ai_panel(report, "pattern_suite")
            if ai_panel:
                self.console.print(ai_panel)
            choice = self._prompt_menu(
                "Pattern Analysis",
                {
                    "1": "Spectrum + Waveform",
                    "2": "Change-Point Timeline",
                    "3": "Motif Similarity",
                    "4": "Volatility Forecast",
                    "0": "Back",
                },
                show_back=True,
            )

            if choice == "0":
                return
            if choice == "m":
                return
            if choice == "x":
                return
            if choice == "1":
                self.console.print(self._render_spectrum_panel(payload))
            elif choice == "2":
                self.console.print(self._render_changepoint_panel(payload))
            elif choice == "3":
                self.console.print(self._render_motif_panel(payload))
            elif choice == "4":
                self.console.print(self._render_vol_forecast_panel(payload))
            InputSafe.pause()

    def _get_pattern_payload(self, returns: pd.Series, interval: str, meta: str) -> Dict[str, Any]:
        key = ("pattern", interval, int(returns.index[-1].timestamp()) if isinstance(returns.index, pd.DatetimeIndex) else len(returns))
        cached = self._pattern_cache.get(key)
        if cached:
            return cached

        values = self._returns_to_values(returns)
        spectrum = self._fft_spectrum(values, top_n=6)
        change_points = self._cusum_change_points(returns, threshold=5.0)
        motifs = self._motif_similarity(returns, window=20, top=3)
        vol_forecast = self._ewma_vol_forecast(returns, lam=0.94, steps=6)
        entropy = self._shannon_entropy(returns, bins=12)
        perm_entropy = self._permutation_entropy(
            values,
            order=self.perm_entropy_order,
            delay=self.perm_entropy_delay,
        )
        hurst = self._hurst_exponent(values)

        payload = {
            "interval": interval,
            "meta": meta,
            "returns": returns,
            "values": values,
            "spectrum": spectrum,
            "change_points": change_points,
            "motifs": motifs,
            "vol_forecast": vol_forecast,
            "entropy": entropy,
            "perm_entropy": perm_entropy,
            "perm_entropy_order": self.perm_entropy_order,
            "perm_entropy_delay": self.perm_entropy_delay,
            "hurst": hurst,
        }
        self._pattern_cache[key] = payload
        return payload

    @staticmethod
    def _returns_to_values(returns: pd.Series) -> List[float]:
        vals = [1.0]
        for r in returns:
            vals.append(vals[-1] * (1.0 + float(r)))
        return vals[1:]

    @staticmethod
    def _fft_spectrum(values: List[float], top_n: int = 6) -> List[Tuple[float, float]]:
        if not values or len(values) < 8:
            return []
        series = np.array(values, dtype=float)
        series = series - series.mean()
        spec = np.fft.rfft(series)
        power = np.abs(spec) ** 2
        freqs = np.fft.rfftfreq(len(series), d=1.0)
        pairs = list(zip(freqs[1:], power[1:]))
        pairs.sort(key=lambda item: item[1], reverse=True)
        return pairs[:top_n]

    @staticmethod
    def _cusum_change_points(returns: pd.Series, threshold: float = 5.0) -> List[int]:
        values = np.array(returns, dtype=float)
        if len(values) < 10:
            return []
        mean = values.mean()
        std = values.std(ddof=1) or 1e-6
        k = 0.5 * std
        h = threshold * std
        pos = 0.0
        neg = 0.0
        change_points = []
        for i, x in enumerate(values):
            pos = max(0.0, pos + x - mean - k)
            neg = min(0.0, neg + x - mean + k)
            if pos > h or abs(neg) > h:
                change_points.append(i)
                pos = 0.0
                neg = 0.0
        return change_points

    @staticmethod
    def _motif_similarity(returns: pd.Series, window: int = 20, top: int = 3) -> List[Dict[str, Any]]:
        values = np.array(returns, dtype=float)
        if len(values) < window * 2:
            return []
        current = values[-window:]
        current = (current - current.mean()) / (current.std(ddof=1) or 1.0)
        step = max(1, window // 3)
        matches = []
        for start in range(0, len(values) - window * 2, step):
            seg = values[start:start + window]
            seg = (seg - seg.mean()) / (seg.std(ddof=1) or 1.0)
            dist = float(np.linalg.norm(current - seg))
            matches.append((start, dist))
        matches.sort(key=lambda item: item[1])
        results = []
        index = returns.index
        for start, dist in matches[:top]:
            end = start + window
            label = f"{start}-{end}"
            if isinstance(index, pd.DatetimeIndex):
                label = f"{index[start].date()} to {index[end-1].date()}"
            results.append({"window": label, "distance": dist})
        return results

    @staticmethod
    def _ewma_vol_forecast(returns: pd.Series, lam: float = 0.94, steps: int = 6) -> List[float]:
        values = np.array(returns, dtype=float)
        if len(values) < 2:
            return []
        var = np.var(values, ddof=1)
        for r in values:
            var = lam * var + (1.0 - lam) * (r ** 2)
        forecast = []
        for _ in range(steps):
            var = lam * var
            forecast.append(math.sqrt(var))
        return forecast

    @staticmethod
    def _shannon_entropy(returns: pd.Series, bins: int = 12) -> float:
        values = np.array(returns, dtype=float)
        if len(values) < 5:
            return 0.0
        counts, _ = np.histogram(values, bins=bins, density=False)
        total = float(counts.sum())
        if total <= 0:
            return 0.0
        probs = counts / total
        probs = probs[probs > 0]
        entropy = float(-np.sum(probs * np.log2(probs)))
        return max(0.0, entropy)

    @staticmethod
    def _permutation_entropy(values: List[float], order: int = 3, delay: int = 1) -> float:
        if not values or order < 2 or delay < 1:
            return 0.0
        n = len(values)
        max_start = n - delay * (order - 1)
        if max_start <= 0:
            return 0.0
        patterns = {}
        for start in range(max_start):
            window = [values[start + i * delay] for i in range(order)]
            ranks = tuple(np.argsort(window))
            patterns[ranks] = patterns.get(ranks, 0) + 1
        total = float(sum(patterns.values()))
        if total <= 0:
            return 0.0
        probs = np.array([count / total for count in patterns.values()], dtype=float)
        entropy = float(-np.sum(probs * np.log2(probs)))
        max_entropy = math.log2(math.factorial(order))
        if max_entropy <= 0:
            return 0.0
        return max(0.0, min(1.0, entropy / max_entropy))

    @staticmethod
    def _hurst_exponent(values: List[float]) -> float:
        if not values or len(values) < 20:
            return 0.5
        series = np.array(values, dtype=float)
        lags = range(2, min(20, len(series) // 2))
        tau = []
        for lag in lags:
            diff = series[lag:] - series[:-lag]
            tau.append(np.sqrt(np.std(diff)))
        if not tau:
            return 0.5
        poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
        return float(poly[0] * 2.0)

    def _render_pattern_summary(self, payload: Dict[str, Any]) -> Table:
        summary = Table(box=box.SIMPLE, expand=True)
        summary.add_column("Signal", style="bold cyan")
        summary.add_column("Value", justify="right")
        summary.add_column("Notes", style="dim")

        summary.add_row("Interval", payload["interval"], payload["meta"])
        summary.add_row("Entropy", f"{payload['entropy']:.2f}", "Return distribution uniformity")
        summary.add_row(
            "Perm Entropy",
            f"{payload['perm_entropy']:.2f}",
            f"Ordering complexity (m={payload['perm_entropy_order']}, tau={payload['perm_entropy_delay']})",
        )
        summary.add_row("Hurst", f"{payload['hurst']:.2f}", "<0.5 mean-revert, >0.5 trend")
        summary.add_row("Change Points", str(len(payload["change_points"])), "CUSUM regime shifts")
        if payload["spectrum"]:
            freq, power = payload["spectrum"][0]
            summary.add_row("Top Frequency", f"{freq:.3f}", f"Power {power:.2f}")
        return summary

    def _render_spectrum_panel(self, payload: Dict[str, Any]) -> Panel:
        values = payload["values"]
        waveform = self._render_waveform(values, width=60, height=10)

        spec = payload["spectrum"]
        spec_table = Table(box=box.SIMPLE, expand=True)
        spec_table.add_column("Freq", justify="right", style="bold cyan")
        spec_table.add_column("Power", justify="right")
        spec_table.add_column("Bar", justify="left")
        max_power = max((p for _, p in spec), default=1.0)
        for freq, power in spec:
            intensity = min(power / max_power, 1.0)
            bar = ChartRenderer.generate_heatmap_bar(intensity, width=18)
            spec_table.add_row(f"{freq:.3f}", f"{power:.2f}", bar)

        layout = Table.grid(expand=True)
        layout.add_column(ratio=1)
        layout.add_row(Panel(waveform, title="Waveform (normalized)", box=box.SQUARE))
        layout.add_row(Panel(spec_table, title="Dominant Frequencies", box=box.SQUARE))
        return Panel(layout, title="Spectrum + Waveform", box=box.ROUNDED, border_style="cyan")

    def _render_changepoint_panel(self, payload: Dict[str, Any]) -> Panel:
        points = payload["change_points"]
        values = payload["values"]
        length = len(values)
        width = 60
        line = ["-"] * width
        for idx in points:
            pos = int((idx / max(1, length - 1)) * (width - 1))
            line[pos] = "|"
        timeline = "".join(line)
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Timeline", style="bold white")
        table.add_column("Events", justify="right")
        table.add_row(timeline, str(len(points)))
        if points:
            table.add_row("", f"Last @ {points[-1]}")
        return Panel(table, title="Change-Point Timeline", box=box.ROUNDED, border_style="yellow")

    def _render_motif_panel(self, payload: Dict[str, Any]) -> Panel:
        motifs = payload["motifs"]
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Window", style="bold cyan")
        table.add_column("Distance", justify="right")
        for match in motifs:
            table.add_row(match["window"], f"{match['distance']:.3f}")
        if not motifs:
            table.add_row("N/A", "Insufficient history")
        return Panel(table, title="Motif Similarity", box=box.ROUNDED, border_style="magenta")

    def _render_vol_forecast_panel(self, payload: Dict[str, Any]) -> Panel:
        forecast = payload["vol_forecast"]
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Step", style="bold cyan")
        table.add_column("Forecast", justify="right")
        table.add_column("Heat", justify="center", width=6)
        max_val = max(forecast) if forecast else 1.0
        for idx, val in enumerate(forecast):
            heat = ChartRenderer.generate_heatmap_bar(min(val / max_val, 1.0), width=6)
            table.add_row(f"T+{idx+1}", f"{val:.4f}", heat)
        return Panel(table, title="Volatility Forecast (EWMA)", box=box.ROUNDED, border_style="cyan")

    def _render_entropy_panel(self, payload: Dict[str, Any]) -> Panel:
        summary = self._render_pattern_summary(payload)
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", justify="right")
        table.add_column("Signal", style="dim")
        table.add_row("Entropy", f"{payload['entropy']:.2f}", "Uniformity of return distribution")
        table.add_row(
            "Perm Entropy",
            f"{payload['perm_entropy']:.2f}",
            f"Ordering complexity (m={payload['perm_entropy_order']}, tau={payload['perm_entropy_delay']})",
        )
        table.add_row("Hurst", f"{payload['hurst']:.2f}", "Trend vs mean-revert")
        context = Table(box=box.SIMPLE, expand=True)
        context.add_column("What it measures", style="bold white")
        context.add_column("How to read it", style="dim")
        context.add_row(
            "Entropy (bins)",
            "Higher = returns spread across bins; lower = clustered outcomes. Sensitive to bin count.",
        )
        context.add_row(
            "Permutation entropy",
            "Higher = more complex order patterns; lower = repetitive ordering. Needs enough points.",
        )
        context.add_row(
            "Hurst exponent",
            "<0.5 mean-reverting tendency; >0.5 trend persistence. Not a forecast.",
        )
        context.add_row(
            "Change points",
            "CUSUM flags shifts in mean level; best used to spot regime breaks.",
        )
        context.add_row(
            "Spectrum",
            "FFT highlights dominant cycle lengths; power shows cycle strength.",
        )
        return Panel(
            Group(
                Panel(summary, title="Pattern Summary", box=box.SIMPLE),
                table,
                Panel(context, title="Pattern Context", box=box.SIMPLE),
            ),
            title="Pattern Analysis",
            box=box.ROUNDED,
            border_style="blue",
        )

    @staticmethod
    def _render_waveform(values: List[float], width: int = 60, height: int = 10) -> Text:
        if not values:
            return Text("No data", style="dim")
        series = np.array(values[-width:], dtype=float)
        if len(series) < width:
            series = np.pad(series, (width - len(series), 0), mode="edge")
        min_val = float(series.min())
        max_val = float(series.max())
        span = max_val - min_val or 1.0
        rows = [[" " for _ in range(width)] for _ in range(height)]
        for i, val in enumerate(series):
            norm = (val - min_val) / span
            pos = int(round((height - 1) * (1 - norm)))
            rows[pos][i] = "█"
        baseline = int(round((height - 1) * (1 - ((0 - min_val) / span))))
        baseline = max(0, min(height - 1, baseline))
        for i in range(width):
            if rows[baseline][i] == " ":
                rows[baseline][i] = "─"
        lines = ["".join(r) for r in rows]
        return Text("\n".join(lines), style="white")

    @staticmethod
    def _annualization_factor_from_index(returns: pd.Series) -> float:
        try:
            idx = returns.index
            if not isinstance(idx, pd.DatetimeIndex) or len(idx) < 2:
                return 252.0
            deltas = idx.to_series().diff().dropna().dt.total_seconds()
            deltas = deltas[deltas > 0]
            if deltas.empty:
                return 252.0
            avg_delta = float(deltas.mean())
            seconds_per_year = 365.25 * 24 * 60 * 60
            return seconds_per_year / avg_delta
        except Exception:
            return 252.0

    @staticmethod
    def assess_risk_profile(metrics: Dict[str, Any], min_points: int = 30) -> str:
        """
        Classifies risk profile based on CAPM beta when sufficient data exists.
        Returns "Not Assessed" if inputs are insufficient.
        """
        if not metrics or metrics.get("error"):
            return "Not Assessed"
        points = int(metrics.get("points", 0) or 0)
        beta = metrics.get("beta")
        if points < min_points or beta is None:
            return "Not Assessed"

        try:
            beta_val = float(beta)
        except Exception:
            return "Not Assessed"

        # Heuristic thresholds commonly used for beta-based risk buckets.
        if beta_val < 0.8:
            return "Conservative"
        if beta_val <= 1.2:
            return "Moderate"
        return "Aggressive"

    @staticmethod
    def _series_from_returns(returns: pd.Series, limit: int = 180) -> List[Dict[str, Any]]:
        if returns is None or returns.empty:
            return []
        tail = returns.tail(limit)
        series = []
        for idx, value in tail.items():
            if hasattr(idx, "timestamp"):
                ts = int(idx.timestamp())
            else:
                try:
                    ts = int(idx)
                except Exception:
                    ts = 0
            try:
                val = float(value)
            except Exception:
                val = 0.0
            series.append({"ts": ts, "value": val})
        return series

    @staticmethod
    def _distribution_from_returns(returns: pd.Series, bins: int = 12) -> List[Dict[str, Any]]:
        if returns is None or returns.empty:
            return []
        vals = np.array([float(v) for v in returns.values if v is not None], dtype=float)
        if vals.size == 0:
            return []
        counts, edges = np.histogram(vals, bins=bins)
        distribution = []
        for idx, count in enumerate(counts):
            distribution.append({
                "bin_start": float(edges[idx]),
                "bin_end": float(edges[idx + 1]),
                "count": int(count),
            })
        return distribution

    def build_risk_dashboard_payload(
        self,
        holdings: Dict[str, float],
        interval: str,
        label: str,
        scope: str = "Portfolio",
        benchmark_ticker: Optional[str] = None,
    ) -> Dict[str, Any]:
        interval = str(interval or self._selected_interval or "1M").upper()
        period = TOOLKIT_PERIOD.get(interval, "1y")
        benchmark = benchmark_ticker or self.benchmark_ticker
        returns, benchmark_returns, meta = self._get_portfolio_and_benchmark_returns(
            holdings,
            benchmark_ticker=benchmark,
            period=period,
            interval=TOOLKIT_INTERVAL.get(interval, "1d"),
        )
        if returns is None or returns.empty:
            return {
                "error": "Insufficient market data",
                "meta": meta,
                "interval": interval,
                "scope": scope,
                "label": label,
            }
        metrics = self._compute_risk_metrics(
            returns,
            benchmark_returns=benchmark_returns,
            risk_free_annual=0.04,
        )
        metrics["points"] = int(len(returns))
        profile = self.assess_risk_profile(metrics)
        return {
            "label": label,
            "scope": scope,
            "interval": interval,
            "benchmark": benchmark,
            "meta": meta,
            "metrics": metrics,
            "risk_profile": profile,
            "returns": self._series_from_returns(returns),
            "benchmark_returns": self._series_from_returns(benchmark_returns) if benchmark_returns is not None else [],
            "distribution": self._distribution_from_returns(returns),
        }

    def build_regime_snapshot_payload(
        self,
        holdings: Dict[str, float],
        lot_map: Dict[str, List[Dict[str, Any]]],
        interval: str,
        label: str,
        scope: str = "Portfolio",
    ) -> Dict[str, Any]:
        interval = str(interval or self._selected_interval or "1M").upper()
        period = TOOLKIT_PERIOD.get(interval, "1y")
        _, enriched = self.valuation.calculate_portfolio_value(
            holdings,
            history_period=period,
            history_interval=TOOLKIT_INTERVAL.get(interval, "1d"),
        )
        _, history = self.valuation.generate_portfolio_history_series(
            enriched_data=enriched,
            holdings=holdings,
            interval=interval,
            lot_map=lot_map,
        )
        if not history:
            return {
                "error": "Insufficient history for regime analysis",
                "scope_label": scope,
                "interval": interval,
                "label": label,
            }
        snap = RegimeModels.snapshot_from_value_series(history, interval=interval, label=label)
        snap["scope_label"] = scope
        snap["interval"] = interval
        return snap

    @staticmethod
    def _wave_surface(values: List[float], width: int = 32) -> Dict[str, Any]:
        if not values:
            return {"z": [], "x": [], "y": []}
        cleaned = [float(v) for v in values if v is not None]
        if not cleaned:
            return {"z": [], "x": [], "y": []}
        length = len(cleaned)
        width = max(8, int(width))
        rows = int(math.ceil(length / width))
        padded = cleaned + [cleaned[-1]] * (rows * width - length)
        grid = []
        for r in range(rows):
            start = r * width
            grid.append(padded[start:start + width])
        return {
            "z": grid,
            "x": list(range(width)),
            "y": list(range(rows)),
        }

    @staticmethod
    def _fft_surface(values: List[float], window: int = 48, step: int = 8, bins: int = 24) -> Dict[str, Any]:
        if not values or len(values) < window:
            return {"z": [], "x": [], "y": []}
        series = np.array(values, dtype=float)
        series = series - series.mean()
        window = max(16, int(window))
        step = max(4, int(step))
        bins = max(8, int(bins))
        rows = []
        positions = []
        freqs = None
        for start in range(0, len(series) - window + 1, step):
            segment = series[start:start + window]
            spec = np.fft.rfft(segment)
            power = np.abs(spec) ** 2
            if freqs is None:
                freqs = np.fft.rfftfreq(len(segment), d=1.0)
            zrow = np.log1p(power[:bins]).tolist()
            rows.append(zrow)
            positions.append(start)
        return {
            "z": rows,
            "x": list(freqs[:bins]) if freqs is not None else [],
            "y": positions,
        }

    def build_pattern_payload(
        self,
        holdings: Dict[str, float],
        interval: str,
        label: str,
        scope: str = "Portfolio",
    ) -> Dict[str, Any]:
        interval = str(interval or self._selected_interval or "1M").upper()
        period = TOOLKIT_PERIOD.get(interval, "1y")
        returns, _, meta = self._get_portfolio_and_benchmark_returns(
            holdings,
            benchmark_ticker=self.benchmark_ticker,
            period=period,
            interval=TOOLKIT_INTERVAL.get(interval, "1d"),
        )
        if returns is None or returns.empty:
            return {
                "error": "Insufficient market data",
                "meta": meta,
                "interval": interval,
                "scope": scope,
                "label": label,
            }
        payload = self._get_pattern_payload(returns, interval, meta)
        values = payload.get("values", []) or []
        spectrum = payload.get("spectrum", []) or []
        formatted_spectrum = [
            {"freq": float(freq), "power": float(power)}
            for freq, power in spectrum
        ]
        wave_surface = self._wave_surface(values)
        fft_surface = self._fft_surface(values)
        if wave_surface.get("z"):
            wave_surface["axis"] = {
                "x_label": "Sample Index",
                "y_label": "Window Row",
                "z_label": "Return Value",
                "x_unit": "index",
                "y_unit": "row",
                "z_unit": "return",
            }
        if fft_surface.get("z"):
            fft_surface["axis"] = {
                "x_label": "Frequency",
                "y_label": "Window Start",
                "z_label": "Log Power",
                "x_unit": "cycles/sample",
                "y_unit": "index",
                "z_unit": "log power",
            }
        return {
            "label": label,
            "scope": scope,
            "interval": interval,
            "meta": meta,
            "entropy": payload.get("entropy"),
            "perm_entropy": payload.get("perm_entropy"),
            "perm_entropy_order": payload.get("perm_entropy_order"),
            "perm_entropy_delay": payload.get("perm_entropy_delay"),
            "hurst": payload.get("hurst"),
            "change_points": payload.get("change_points", []) or [],
            "motifs": payload.get("motifs", []) or [],
            "vol_forecast": payload.get("vol_forecast", []) or [],
            "spectrum": formatted_spectrum,
            "wave_surface": wave_surface,
            "fft_surface": fft_surface,
        }

    def _select_interval(self) -> Optional[str]:
        options = list(TOOLKIT_PERIOD.keys())
        options_map = {opt: opt for opt in options}
        options_map["0"] = "Back"
        choice = self._prompt_menu("Select Interval", options_map, show_back=True)
        if choice in ("0", "m"):
            return None
        return choice.upper()

    def _get_interval_or_select(self, force: bool = False) -> Optional[str]:
        if not force and self._selected_interval:
            return self._selected_interval
        choice = self._select_interval()
        if choice:
            self._selected_interval = choice
        return choice

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
        ann_factor = FinancialToolkit._annualization_factor_from_index(returns)
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

    def _render_metric_glossary(self, keys: List[str], title: str = "Metric Context") -> Panel:
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="bold cyan", width=18)
        table.add_column("Definition", style="white")
        table.add_column("High/Low", style="dim")
        table.add_column("Units/Range", style="dim")
        table.add_column("Limits", style="dim")

        seen = set()
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            info = _METRIC_GLOSSARY.get(key)
            if not info:
                continue
            units_range = f"{info.get('units')} | {info.get('range')}"
            table.add_row(
                info.get("label", key),
                info.get("definition", ""),
                info.get("high_low", ""),
                units_range,
                info.get("limits", ""),
            )

        return Panel(table, title=f"[bold]{title}[/bold]", box=box.ROUNDED, border_style="dim")

    def _render_risk_metrics_table(self, metrics: Dict[str, Any]) -> Panel:
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", justify="right")
        table.add_column("Notes", style="dim")

        def fmt(value: Any, fmt_str: str, fallback: str = "N/A") -> str:
            return fallback if value is None else fmt_str.format(value)

        table.add_row("Annual Return (μ)", fmt(metrics.get("mean_annual"), "{:+.2%}"), "Avg period return * ann. factor")
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

        metrics_panel = Panel(table, title="[bold]Model Metrics[/bold]", box=box.ROUNDED, border_style="blue")
        glossary = self._render_metric_glossary(
            [
                "mean_annual",
                "vol_annual",
                "sharpe",
                "sortino",
                "beta",
                "alpha_annual",
                "r_squared",
                "tracking_error",
                "information_ratio",
                "treynor",
                "m_squared",
                "max_drawdown",
                "var_95",
                "cvar_95",
                "var_99",
                "cvar_99",
            ],
            title="Risk Metric Context",
        )
        return Group(metrics_panel, glossary)

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

        return Panel(table, title="[bold]Return Distribution[/bold]", box=box.ROUNDED, border_style="magenta")

    def _render_capm_context(self, capm: Dict[str, Any]) -> Panel:
        points = capm.get("points") if isinstance(capm, dict) else None
        points_label = str(points) if points else "N/A"
        lines = [
            f"CAPM compares the portfolio to {self.benchmark_ticker} to estimate beta and alpha.",
            "Alpha is annualized excess return over CAPM expectations; beta is sensitivity to benchmark moves.",
            "R-squared shows how much of the return variance the benchmark explains.",
            f"Sample points: {points_label}; risk-free rate defaults to 4% annual unless configured.",
            "Short histories or regime shifts can make beta/alpha unstable; treat as descriptive.",
        ]
        return Panel("\n".join(lines), title="[bold]CAPM Context[/bold]", box=box.SIMPLE, border_style="dim")

    def _render_risk_dashboard_context(self, interval: str, meta: str) -> Panel:
        lines = [
            f"Metrics use historical returns for the selected interval ({interval}).",
            "VaR/CVaR are historical tail summaries, not guaranteed loss limits.",
            "Return distribution buckets show frequency, not probability of future outcomes.",
            f"Data window: {meta}.",
        ]
        return Panel("\n".join(lines), title="[bold]Risk Dashboard Context[/bold]", box=box.SIMPLE, border_style="dim")

    def _render_diagnostics_context(
        self,
        interval: str,
        total_val: float,
        manual_total: float,
        sector_rows: List[Tuple[str, float]],
        hhi: float,
    ) -> Panel:
        hhi_note = f"HHI {hhi:.3f}" if hhi > 0 else "HHI N/A"
        manual_note = f"Manual assets included: {manual_total:,.0f}" if manual_total > 0 else "Manual assets excluded"
        sector_note = "Sector mix based on available sector tags." if sector_rows else "Sector mix unavailable."
        lines = [
            f"Diagnostics summarize {interval} performance, concentration, and recent movers.",
            manual_note,
            sector_note,
            f"{hhi_note} (higher = more concentrated).",
            "Values use current market prices and do not include tax effects.",
        ]
        return Panel("\n".join(lines), title="[bold]Diagnostics Context[/bold]", box=box.SIMPLE, border_style="dim")

    def _render_black_scholes_context(
        self,
        spot_price: float,
        strike_price: float,
        time_years: float,
        volatility: float,
        risk_free: float,
    ) -> Panel:
        lines = [
            "Black-Scholes estimates European option fair value using spot, strike, time, volatility, and the risk-free rate.",
            "Assumes constant volatility and rates, no dividends, and no early exercise.",
            "Time uses a 365-day year; results are theoretical and ignore bid/ask spreads.",
            f"Inputs: S={spot_price:.2f}, K={strike_price:.2f}, T={time_years:.2f}y, sigma={volatility:.2%}, r={risk_free:.2%}.",
            "Higher spot or volatility increases call value; higher strike increases put value.",
        ]
        return Panel("\n".join(lines), title="[bold]Model Context[/bold]", box=box.SIMPLE, border_style="dim")

    def _render_regime_context(self, snap: Dict[str, Any]) -> Panel:
        interval = snap.get("interval", "N/A")
        scope = snap.get("scope_label", "Portfolio")
        lines = [
            f"Regimes are inferred states from the {scope.lower()} value series over the {interval} interval.",
            "Confidence reflects model separation between regimes, not a forward forecast.",
            "Short histories or missing data can make regimes unstable; use as descriptive signals.",
            "Expected next is the most likely transition given the current state.",
        ]
        return Panel("\n".join(lines), title="[bold]Regime Context[/bold]", box=box.SIMPLE, border_style="dim")

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
                    df = yf.download(
                        download_list,
                        period=period,
                        interval="1d",
                        progress=False,
                        group_by="column",
                        auto_adjust=True,
                    )
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

            capm = FinancialToolkit.compute_capm_metrics_from_returns(
                port_ret,
                mkt_ret,
                risk_free_annual=risk_free_annual,
                min_points=30,
            )
            capm.update({
                "benchmark": bench,
                "period": period,
                "risk_free_annual": float(risk_free_annual),
            })

            _CAPM_CACHE[key] = {"ts": ts, "data": capm}
            return capm

        except Exception as ex:
            data = {"error": f"CAPM compute error: {ex}", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
            _CAPM_CACHE[key] = {"ts": ts, "data": data}
            return data

    @staticmethod
    def compute_capm_metrics_from_returns(
        returns: pd.Series,
        benchmark_returns: pd.Series,
        risk_free_annual: float = 0.04,
        min_points: int = 30,
    ) -> Dict[str, Any]:
        if returns is None or benchmark_returns is None:
            return {"error": "Missing returns", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}
        if returns.empty or benchmark_returns.empty:
            return {"error": "No return history", "beta": None, "alpha_annual": None, "r_squared": None, "sharpe": None, "vol_annual": None, "points": 0}

        joined = pd.concat(
            [returns.rename("p"), benchmark_returns.rename("m")],
            axis=1,
        ).dropna()
        if joined.empty or len(joined) < min_points:
            return {
                "error": "Insufficient return history",
                "beta": None,
                "alpha_annual": None,
                "r_squared": None,
                "sharpe": None,
                "vol_annual": None,
                "points": int(len(joined)),
            }

        ann_factor = FinancialToolkit._annualization_factor_from_index(joined["p"])
        p = joined["p"].values
        m = joined["m"].values

        var_m = float(np.var(m, ddof=1))
        cov_pm = float(np.cov(p, m, ddof=1)[0][1])
        beta = (cov_pm / var_m) if var_m > 0 else None

        rf_daily = float(risk_free_annual) / ann_factor
        avg_p = float(np.mean(p))
        avg_m = float(np.mean(m))

        alpha_daily = None
        alpha_annual = None
        if beta is not None:
            alpha_daily = avg_p - (rf_daily + beta * (avg_m - rf_daily))
            alpha_annual = alpha_daily * ann_factor

        corr = float(np.corrcoef(p, m)[0][1])
        r_squared = corr * corr

        std_p = float(np.std(p, ddof=1))
        sharpe = ((avg_p - rf_daily) / std_p * (ann_factor ** 0.5)) if std_p > 0 else None
        vol_annual = std_p * (ann_factor ** 0.5)

        neg = p[p < rf_daily]
        downside_std = float(np.std(neg, ddof=1)) if len(neg) > 1 else None
        downside_vol_annual = downside_std * (ann_factor ** 0.5) if downside_std else None

        sortino = None
        if downside_std and downside_std > 0:
            sortino = (avg_p - rf_daily) / downside_std * (ann_factor ** 0.5)

        jensen_alpha = alpha_annual

        excess = p - m
        te = float(np.std(excess, ddof=1))
        information_ratio = None
        if te > 0:
            information_ratio = (avg_p - avg_m) / te * (ann_factor ** 0.5)

        std_m = float(np.std(m, ddof=1))
        m_squared = None
        if std_p > 0:
            m_squared = ((avg_p - rf_daily) / std_p) * std_m * ann_factor + risk_free_annual

        return {
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
        }

    # toolkit.py changes

    @staticmethod
    def _compute_core_metrics(returns: pd.Series, benchmark_returns: pd.Series = None) -> dict:
        """Centralized math engine for all UI components."""
        if returns.empty:
            return {}

        # Standard Volatility (Annualized)
        ann_factor = FinancialToolkit._annualization_factor_from_index(returns)
        vol = returns.std() * np.sqrt(ann_factor)
        
        # Sharpe (assuming 0% risk-free rate currently just for dev simplicity)
        sharpe = (returns.mean() / returns.std()) * np.sqrt(ann_factor) if returns.std() != 0 else 0

        metrics = {
            "volatility_annual": float(vol),
            "sharpe": float(sharpe),
            "mean_return": float(returns.mean() * ann_factor),
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

    ANNUALIZATION = {
        "1W": 252.0 * 6.5,  # 60m bars, approx 6.5 trading hours/day
        "1M": 252.0,
        "3M": 252.0,
        "6M": 252.0,
        "1Y": 252.0,
        "1D": 252.0,
        "1WK": 52.0,
        "1MO": 12.0,
        "60M": 252.0 * 6.5,
    }

    @staticmethod
    def _annualization_factor(interval: str | None) -> float:
        if not interval:
            return 252.0
        key = str(interval).upper().strip()
        return float(RegimeModels.ANNUALIZATION.get(key, 252.0))

    @staticmethod
    def _annualization_from_timestamps(timestamps: list) -> Optional[float]:
        if not timestamps or len(timestamps) < 2:
            return None
        deltas = []
        for i in range(1, len(timestamps)):
            a = timestamps[i - 1]
            b = timestamps[i]
            if not hasattr(a, "timestamp") or not hasattr(b, "timestamp"):
                continue
            delta = (b - a).total_seconds()
            if delta > 0:
                deltas.append(delta)
        if not deltas:
            return None
        avg_delta = sum(deltas) / len(deltas)
        seconds_per_year = 365.25 * 24 * 60 * 60
        return seconds_per_year / avg_delta

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
    def _evolution_surface(
        P: list[list[float]],
        current_state: int,
        steps: int,
        include_initial: bool = False
    ) -> list[list[float]]:
        """
        Returns a matrix (steps+1) x n where row t is the state probability vector at time t,
        starting from a one-hot distribution at current_state.
        """
        n = len(P)
        if n <= 0:
            return []

        out = []
        probs = [0.0] * n
        probs[current_state] = 1.0
        if include_initial:
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

        snap = RegimeModels.compute_markov_snapshot(
            returns,
            horizon=1,
            label=f"{label} ({interval})",
            interval=interval,
        )
        snap["interval"] = interval
        return snap

    @staticmethod
    def compute_markov_snapshot(
        returns: list[float],
        horizon: int = 1,
        label: str = "1D",
        interval: str | None = None,
        timestamps: list | None = None,
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
        if len(returns) > 1:
            volatility = math.sqrt(
                sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
            )
        else:
            volatility = 0.0
        ann_factor = RegimeModels._annualization_from_timestamps(timestamps) or RegimeModels._annualization_factor(interval)
        avg_return_annual = avg_return * ann_factor
        volatility_annual = volatility * math.sqrt(ann_factor)

        # --- Surfaces (pure Markov; interval-compatible) ---
        pi = RegimeModels._stationary_distribution(P)
        evo_steps = 12
        evo = RegimeModels._evolution_surface(P, current_state, evo_steps, include_initial=False)

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
            "samples": len(returns),
            "metrics": {
                "avg_return": avg_return_annual,
                "volatility": volatility_annual,
                "avg_return_raw": avg_return,
                "volatility_raw": volatility,
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

        snap = RegimeModels.compute_markov_snapshot(
            returns.tolist(),
            horizon=1,
            label=f"{symbol} ({period})",
            interval=interval,
            timestamps=list(df.index),
        )
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
                ann_factor = FinancialToolkit._annualization_factor_from_index(combined.iloc[:, 0])
                avg_p = float(combined.iloc[:, 0].mean() * ann_factor)
                avg_m = float(combined.iloc[:, 1].mean() * ann_factor)
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
    def _fmt_pct(value: Any, decimals: int = 2) -> str:
        try:
            p = float(value or 0.0)
        except (ValueError, TypeError):
            p = 0.0
        if p < 1.0:
            cap = 100.0 - (10 ** (-decimals))
            pct = min(p * 100.0, cap)
        else:
            pct = 100.0
        return f"{pct:.{decimals}f}%"

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
        left.add_row("Confidence", RegimeRenderer._fmt_pct(snapshot["confidence"]))
        left.add_row("Stability", RegimeRenderer._fmt_pct(snapshot["stability"]))
        if "samples" in snapshot:
            left.add_row("Samples", str(snapshot.get("samples")))
        left.add_row(
            "Avg Return (Ann.)",
            RegimeRenderer._fmt_pct(snapshot["metrics"]["avg_return"])
        )
        left.add_row(
            "Volatility (Ann.)",
            RegimeRenderer._fmt_pct(snapshot["metrics"]["volatility"])
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
            bar = ChartRenderer.generate_heatmap_bar(p, width=18)
            prob_table.add_row(
                name,
                RegimeRenderer._fmt_pct(p),
                bar
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

            if p >= 0.95:   ch, col = "█", "bold red"
            elif p >= 0.85: ch, col = "▇", "red"
            elif p >= 0.70: ch, col = "▆", "yellow"
            elif p >= 0.55: ch, col = "▅", "green"
            elif p >= 0.40: ch, col = "▄", "cyan"
            elif p >= 0.25: ch, col = "▃", "blue"
            elif p >= 0.10: ch, col = "▂", "dim cyan"
            else:               ch, col = "▁", "dim white"

            blocks = f"[{col}]{ch * 6}[/{col}]"
            return Text.from_markup(f"{blocks}\n[white bold]{RegimeRenderer._fmt_pct(p)}[/white bold]")

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
        console_width = Console().width
        target_width = max(10, console_width // 2)
        cell_width = max(2, int((target_width - max(0, n - 1)) / max(1, n)) // 2)
        surf = Table(
            box=box.SIMPLE,
            show_header=False,
            pad_edge=True,
            expand=True,
            padding=(0, 0),
        )
        surf.add_column("Surface", ratio=1, no_wrap=True)

        # Render each row as a "ridge" of stacked blocks.
        # Height is proportional to probability (0..1) mapped to 0..8 blocks.
        def stack(p: float) -> str:
            levels = "▁▂▃▄▅▆▇█"
            idx = int(round(max(0.0, min(1.0, float(p))) * (len(levels) - 1)))
            return levels[idx] * cell_width

        def stack_color(p: float) -> str:
            if p >= 0.90:
                return "bold red"
            if p >= 0.70:
                return "red"
            if p >= 0.50:
                return "yellow"
            if p >= 0.30:
                return "green"
            if p >= 0.15:
                return "cyan"
            return "dim white"

        i = 0
        lines = []
        while i < n:
            row = P[i]
            j = 0
            parts = []
            while j < n:
                block = stack(row[j])
                color = stack_color(float(row[j] or 0.0))
                parts.append(f"[{color}]{block}[/{color}]")
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
            bar = ChartRenderer.generate_heatmap_bar(p, width=18)
            tab.add_row(name, RegimeRenderer._fmt_pct(p), bar)

        return tab

    @staticmethod
    def _render_evolution_surface(evolution: dict, labels: list[str]) -> Table:
        series = evolution.get("series", []) if isinstance(evolution, dict) else []
        series_to_render = series
        if series:
            try:
                first = series[0]
                if isinstance(first, dict):
                    vals = list(first.values())
                elif isinstance(first, (list, tuple)):
                    vals = list(first)
                else:
                    vals = []
                if vals:
                    max_p = max(float(v or 0.0) for v in vals)
                    if max_p >= 0.999 and len(series) > 1:
                        series_to_render = series[1:]
            except Exception:
                series_to_render = series
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
            pct = f"[white bold]{RegimeRenderer._fmt_pct(p_val)}[/white bold]"
            
            return Text.from_markup(f"{blocks}\n{pct}")

        # 4. Render each time step
        total = len(series_to_render)
        for t_idx, probs in enumerate(series_to_render):
            row_label = f"T-{total-t_idx-1}"
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
