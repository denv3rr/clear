from __future__ import annotations

from typing import Any, Dict, List

from rich.align import Align
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

from interfaces.shell import ShellRenderer
from modules.client_mgr import calculations
from modules.client_mgr.regime import RegimeModels
from modules.client_mgr.regime_views import RegimeRenderer
from modules.client_mgr.patterns import PatternRenderer
from modules.client_mgr.risk_views import RiskRenderer
from modules.client_mgr.toolkit_menu import prompt_menu
from modules.client_mgr.toolkit_payloads import TOOLKIT_INTERVAL, TOOLKIT_PERIOD
from utils.input import InputSafe


class ToolkitRunMixin:
    def _run_capm_analysis(self) -> None:
        """
        Calculates CAPM and risk metrics using shared toolkit functions.
        """
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print(
            f"[bold blue]CAPM & RISK METRICS (Benchmark: {self.benchmark_ticker})[/bold blue]"
        )

        consolidated_holdings = {}
        for acc in self.client.accounts:
            for ticker, qty in acc.holdings.items():
                consolidated_holdings[ticker] = (
                    consolidated_holdings.get(ticker, 0) + qty
                )

        if not consolidated_holdings:
            self.console.print("[yellow]No holdings available for analysis.[/yellow]")
            InputSafe.pause()
            return

        interval = self._get_interval_or_select()
        if not interval:
            return
        period = TOOLKIT_PERIOD.get(interval, "1y")

        with Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="Fetching market data...", total=None)
            returns, bench_returns, meta = self._get_portfolio_and_benchmark_returns(
                consolidated_holdings,
                benchmark_ticker=self.benchmark_ticker,
                period=period,
                interval=TOOLKIT_INTERVAL.get(interval, "1d"),
            )

        if returns is None or returns.empty:
            self.console.print("[yellow]Insufficient data for CAPM analysis.[/yellow]")
            InputSafe.pause()
            return

        metrics = self._compute_risk_metrics(
            returns,
            benchmark_returns=bench_returns,
            risk_free_annual=0.04,
        )
        capm = metrics.get("capm", {})
        beta = capm.get("beta")
        alpha = capm.get("alpha")
        r_squared = capm.get("r_squared")
        vol_annual = metrics.get("volatility_annual")
        sharpe = metrics.get("sharpe_ratio")
        alpha_annualized = None
        if alpha is not None:
            alpha_annualized = (1 + alpha) ** 252 - 1
        risk_level = (
            "High"
            if beta is not None and beta > 1.2
            else "Moderate"
            if beta is not None and beta > 0.8
            else "Low"
        )
        signals = []
        if beta is not None:
            signals.append(f"Beta {beta:.2f}")
        if r_squared is not None:
            signals.append(f"R-Squared {r_squared:.2f}")
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
                        [
                            "Alpha (Annual)",
                            f"{alpha_annualized:.2%}"
                            if alpha_annualized is not None
                            else "N/A",
                        ],
                        ["R-Squared", f"{r_squared:.2f}" if r_squared is not None else "N/A"],
                        ["Sharpe", f"{sharpe:.2f}" if sharpe is not None else "N/A"],
                        [
                            "Volatility",
                            f"{vol_annual:.2%}" if vol_annual is not None else "N/A",
                        ],
                    ],
                }
            ],
        }
        ai_panel = self._build_ai_panel(report, "capm_analysis")
        if ai_panel:
            self.console.print(ai_panel)
        self.console.print(RiskRenderer.render_capm_context(capm, self.benchmark_ticker))

        if beta and beta > 1.2:
            self.console.print(
                "\n[bold yellow]⚠ High Volatility:[/bold yellow] "
                "This client portfolio is significantly more volatile than the market."
            )
        elif beta and beta < 0.8:
            self.console.print(
                "\n[bold green]🛡 Defensive:[/bold green] "
                "This client portfolio is less volatile than the market."
            )

        InputSafe.pause()

    def _run_black_scholes(self) -> None:
        """
        Calculates European Call/Put prices using Black-Scholes-Merton.
        Auto-fetches 'S' (Spot Price) if the user selects a holding.
        """
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print(
            Panel("[bold]BLACK-SCHOLES DERIVATIVES MODEL[/bold]", box=box.HEAVY)
        )

        ticker = self.console.input(
            "[bold cyan]Underlying Ticker (Enter to skip lookup): [/bold cyan]"
        ).strip().upper()
        spot_price = 0.0

        if ticker:
            quote = self.valuation.get_quote_data(ticker)
            if quote["price"] > 0:
                spot_price = quote["price"]
                self.console.print(
                    f"   [green]✔ Live Spot Price ({ticker}): ${spot_price:,.2f}[/green]"
                )
            else:
                self.console.print(
                    "   [yellow]⚠ Could not fetch price. Enter manually.[/yellow]"
                )

        if spot_price == 0.0:
            spot_price = InputSafe.get_float("Enter Spot Price ($):", min_val=0.01)

        strike_price = InputSafe.get_float("Enter Strike Price ($):", min_val=0.01)

        days = InputSafe.get_float("Days to Expiration:", min_val=1)
        time_years = days / 365.0

        volatility = (
            InputSafe.get_float(
                "Implied Volatility % (e.g. 25 for 25%):", min_val=0.01
            )
            / 100.0
        )

        risk_free = InputSafe.get_float("Risk-Free Rate % (e.g. 4.5):", min_val=0.0) / 100.0

        call_price, put_price = calculations.black_scholes_price(
            S=spot_price,
            K=strike_price,
            T=time_years,
            r=risk_free,
            sigma=volatility,
        )

        table = Table(title="Option Pricing Results", box=box.SIMPLE)
        table.add_column("Option Type", style="cyan")
        table.add_column("Price ($)", justify="right")
        table.add_row("Call", f"{call_price:,.2f}")
        table.add_row("Put", f"{put_price:,.2f}")
        self.console.print(table)

        InputSafe.pause()

    def _run_multi_model_dashboard(self) -> None:
        """Compute a multi-model risk dashboard for the client's portfolio."""
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print("[bold blue]MULTI-MODEL RISK DASHBOARD[/bold blue]")

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
        risk_level = self.assess_risk_profile(metrics)
        model = self._model_selector.get_model()
        estimate = model.estimate_current_regime(returns)
        report = {
            "summary": [
                f"Holdings: {len(holdings)}",
                f"Interval: {interval}",
            ],
            "risk_level": risk_level,
            "risk_score": None,
            "confidence": "Medium",
            "signals": [
                f"Regime: {estimate.get('current_regime') or 'Unknown'}",
                f"Beta: {metrics.get('beta'):.2f}" if metrics.get("beta") is not None else "Beta N/A",
            ],
            "impacts": [
                "Multi-model overlay derived from CAPM + regime detection.",
            ],
            "sections": [
                {
                    "title": "Regime Summary",
                    "rows": [
                        ["Model", estimate.get("model") or model.name],
                        ["Regime", estimate.get("current_regime") or "N/A"],
                        [
                            "Confidence",
                            f"{estimate.get('confidence'):.2f}"
                            if estimate.get("confidence") is not None
                            else "N/A",
                        ],
                    ],
                },
            ],
        }
        ai_panel = self._build_ai_panel(report, "multi_model_dashboard")
        if ai_panel:
            self.console.print(ai_panel)
        self.console.print(RiskRenderer.render_risk_metrics_table(metrics))
        self.console.print(RiskRenderer.render_return_distribution(returns))
        self.console.print(RiskRenderer.render_risk_dashboard_context(interval, meta))
        InputSafe.pause()

    def _run_regime_snapshot(self) -> None:
        """Generate a regime snapshot from portfolio value history."""
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print("[bold blue]PORTFOLIO REGIME SNAPSHOT[/bold blue]")

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

        snap = RegimeModels.snapshot_from_value_series(
            history,
            interval=interval,
            label=self.client.name,
        )
        snap["scope_label"] = "Portfolio"
        snap["interval"] = interval
        self.console.print(RegimeRenderer.render(snap))
        self.console.print(self._render_regime_context(snap))
        InputSafe.pause()

    def _run_portfolio_diagnostics(self) -> None:
        """Run a consolidated diagnostics report using shared metrics."""
        self.console.clear()
        print("\x1b[3J", end="")
        self.console.print("[bold blue]PORTFOLIO DIAGNOSTICS[/bold blue]")

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
        self.console.print(RiskRenderer.render_risk_metrics_table(metrics))
        self.console.print(RiskRenderer.render_return_distribution(returns))
        self.console.print(RiskRenderer.render_risk_dashboard_context(interval, meta))
        InputSafe.pause()

    def _run_pattern_suite(self) -> None:
        """Pattern analysis is using existing return series."""
        while True:
            self.console.clear()
            print("\x1b[3J", end="")
            self.console.print("[bold blue]PATTERN SUITE ANALYSIS[/bold blue]")

            interval = self._get_interval_or_select()
            if not interval:
                return

            holdings = self._aggregate_holdings()
            if not holdings:
                self.console.print("[yellow]No holdings available for analysis.[/yellow]")
                InputSafe.pause()
                return

            period = TOOLKIT_PERIOD.get(interval, "1y")
            returns, _, meta = self._get_portfolio_and_benchmark_returns(
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
            if entropy is not None:
                signals.append(f"Entropy {entropy:.2f}")
            if perm_entropy is not None:
                signals.append(f"Perm Entropy {perm_entropy:.2f}")
            if hurst is not None:
                signals.append(f"Hurst {hurst:.2f}")
            impacts = []
            if change_points:
                impacts.append(f"{len(change_points)} change points detected.")
            if spectrum:
                impacts.append(f"{len(spectrum)} dominant cycles detected.")
            report = {
                "summary": [
                    f"Interval: {interval}",
                    f"Holdings: {len(holdings)}",
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
                            [
                                "Top Cycles",
                                ", ".join([f"{float(freq):.2f}" for freq, _ in spectrum[:3]])
                                or "N/A",
                            ],
                        ],
                    }
                ],
            }
            ai_panel = self._build_ai_panel(report, "pattern_suite")
            if ai_panel:
                self.console.print(ai_panel)
            choice = prompt_menu(
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

    def _render_regime_context(self, snap: Dict[str, Any]) -> Panel:
        interval = snap.get("interval", "N/A")
        scope = snap.get("scope_label", "Portfolio")
        header = Align.center(
            f"[bold cyan]Regime Snapshot Context ({scope})[/bold cyan]",
            vertical="middle",
        )
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Metric", style="dim", width=22)
        table.add_column("Value", style="white")
        table.add_row("Interval", str(interval))
        table.add_row("Model", str(snap.get("model", "Unknown")))
        table.add_row("Current Regime", str(snap.get("current_regime", "N/A")))
        table.add_row("Expected Next", str(snap.get("expected_next", {}).get("regime", "N/A")))
        table.add_row(
            "Next Probability",
            f"{snap.get('expected_next', {}).get('probability', 0):.2f}",
        )
        content = Panel(
            table,
            box=box.ROUNDED,
            title="Regime Context",
            border_style="cyan",
        )
        return Panel(
            Align.center(content, vertical="middle"),
            box=box.SQUARE,
            title=header,
            border_style="cyan",
        )
