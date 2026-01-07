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
from modules.client_mgr import calculations
from modules.client_mgr.regime import RegimeModels
from modules.client_mgr.regime_views import RegimeRenderer
from modules.client_mgr.patterns import PatternSuite, PatternRenderer
from modules.client_mgr.risk_views import RiskRenderer
from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.valuation import ValuationEngine
from utils.report_synth import ReportSynthesizer, build_report_context, build_ai_sections

# Cache for CAPM computations to avoid redundant API calls
_CAPM_CACHE = {}  # key -> {"ts": int, "data": dict}
_CAPM_TTL_SECONDS = 900  # 15 minutes

# Metric glossary for Tools output (plain-language context).

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
        self.patterns = PatternSuite(
            perm_entropy_order=self.perm_entropy_order,
            perm_entropy_delay=self.perm_entropy_delay,
        )
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
            RiskRenderer.render_metric_glossary(
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
        self.console.print(RiskRenderer.render_capm_context(capm, self.benchmark_ticker))

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

        call_price, put_price = calculations.black_scholes_price(
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
        self.console.print(RiskRenderer.render_black_scholes_context(spot_price, strike_price, time_years, volatility, risk_free))
        InputSafe.pause()

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
        self.console.print(RiskRenderer.render_risk_metrics_table(metrics))
        self.console.print(RiskRenderer.render_return_distribution(returns))
        self.console.print(RiskRenderer.render_risk_dashboard_context(interval, meta))
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
            RiskRenderer.render_metric_glossary(
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
        self.console.print(RiskRenderer.render_diagnostics_context(interval, total_val, manual_total, sector_rows, hhi))
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
                RiskRenderer.render_metric_glossary(
                    ["entropy", "perm_entropy", "hurst"],
                    title="Pattern Metric Context",
                )
            )
            self.console.print(PatternRenderer.render_entropy_panel(payload))
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
                self.console.print(PatternRenderer.render_spectrum_panel(payload))
            elif choice == "2":
                self.console.print(PatternRenderer.render_changepoint_panel(payload))
            elif choice == "3":
                self.console.print(PatternRenderer.render_motif_panel(payload))
            elif choice == "4":
                self.console.print(PatternRenderer.render_vol_forecast_panel(payload))
            InputSafe.pause()

    def _get_pattern_payload(self, returns: pd.Series, interval: str, meta: str) -> Dict[str, Any]:
        key = ("pattern", interval, int(returns.index[-1].timestamp()) if isinstance(returns.index, pd.DatetimeIndex) else len(returns))
        cached = self._pattern_cache.get(key)
        if cached:
            return cached

        payload = self.patterns.build_payload(returns, interval, meta)
        self._pattern_cache[key] = payload
        return payload

    @staticmethod
    def _annualization_factor_from_index(returns: pd.Series) -> float:
        return calculations.annualization_factor_from_index(returns)

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
            has_holdings = any(float(qty or 0.0) > 0 for qty in (holdings or {}).values())
            has_price_history = any(
                info.get("history")
                for info in (enriched or {}).values()
                if isinstance(info, dict)
            )
            if not has_holdings:
                detail = "No holdings available to compute a regime series."
            elif not has_price_history:
                detail = "No historical price series available for holdings (manual lots or missing price history)."
            else:
                detail = "Not enough historical points to compute a regime series."
            return {
                "error": "Insufficient history for regime analysis",
                "error_detail": detail,
                "scope_label": scope,
                "interval": interval,
                "label": label,
            }
        snap = RegimeModels.snapshot_from_value_series(history, interval=interval, label=label)
        snap["scope_label"] = scope
        snap["interval"] = interval
        return snap

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
        wave_surface, fft_surface = self.patterns.build_surfaces(values)
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
        return calculations.compute_risk_metrics(
            returns,
            benchmark_returns,
            risk_free_annual,
        )

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

            capm = calculations.compute_capm_metrics_from_returns(
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
        return calculations.compute_capm_metrics_from_returns(
            returns,
            benchmark_returns,
            risk_free_annual=risk_free_annual,
            min_points=min_points,
        )
    @staticmethod
    def _compute_core_metrics(returns: pd.Series, benchmark_returns: pd.Series = None) -> dict:
        return calculations.compute_core_metrics(returns, benchmark_returns)
