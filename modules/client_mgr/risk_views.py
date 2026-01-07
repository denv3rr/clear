from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table


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
        "high_low": "Higher means more complex ordering; lower means more repetitive ordering.",
        "range": "0 to 1.",
        "units": "Normalized bits.",
        "limits": "Needs sufficient samples; m and tau matter.",
    },
    "hurst": {
        "label": "Hurst Exponent",
        "definition": "Trend persistence measure based on rescaled range analysis.",
        "high_low": "<0.5 mean-reverting; >0.5 trending.",
        "range": "0 to 1.",
        "units": "Ratio.",
        "limits": "Requires long histories; unstable with short series.",
    },
}


class RiskRenderer:
    @staticmethod
    def render_metric_glossary(keys: List[str], title: str = "Metric Context") -> Panel:
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

    @staticmethod
    def render_risk_metrics_table(metrics: Dict[str, Any]) -> Group:
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", justify="right")
        table.add_column("Notes", style="dim")

        def fmt(value: Any, fmt_str: str, fallback: str = "N/A") -> str:
            return fallback if value is None else fmt_str.format(value)

        table.add_row("Annual Return (mu)", fmt(metrics.get("mean_annual"), "{:+.2%}"), "Avg period return * ann. factor")
        table.add_row("Volatility (sigma)", fmt(metrics.get("vol_annual"), "{:.2%}"), "Annualized std dev")
        table.add_row("Sharpe Ratio", fmt(metrics.get("sharpe"), "{:.2f}"), "Risk-adjusted return")
        table.add_row("Sortino Ratio", fmt(metrics.get("sortino"), "{:.2f}"), "Downside-adjusted")
        table.add_row("Beta", fmt(metrics.get("beta"), "{:.2f}"), "Systemic sensitivity")
        table.add_row("Alpha (Jensen)", fmt(metrics.get("alpha_annual"), "{:+.2%}"), "Excess return vs CAPM")
        table.add_row("R-Squared", fmt(metrics.get("r_squared"), "{:.2f}"), "Fit vs benchmark")
        table.add_row("Tracking Error", fmt(metrics.get("tracking_error"), "{:.2%}"), "Std dev of excess")
        table.add_row("Information Ratio", fmt(metrics.get("information_ratio"), "{:.2f}"), "Excess / tracking error")
        table.add_row("Treynor Ratio", fmt(metrics.get("treynor"), "{:.2%}"), "Return per beta")
        table.add_row("M2", fmt(metrics.get("m_squared"), "{:+.2%}"), "Modigliani-Modigliani")
        table.add_row("Max Drawdown", fmt(metrics.get("max_drawdown"), "{:.2%}"), "Peak-to-trough")
        table.add_row("VaR 95%", fmt(metrics.get("var_95"), "{:+.2%}"), "Historical quantile")
        table.add_row("CVaR 95%", fmt(metrics.get("cvar_95"), "{:+.2%}"), "Expected tail loss")
        table.add_row("VaR 99%", fmt(metrics.get("var_99"), "{:+.2%}"), "Historical quantile")
        table.add_row("CVaR 99%", fmt(metrics.get("cvar_99"), "{:+.2%}"), "Expected tail loss")

        metrics_panel = Panel(table, title="[bold]Model Metrics[/bold]", box=box.ROUNDED, border_style="blue")
        glossary = RiskRenderer.render_metric_glossary(
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

    @staticmethod
    def render_return_distribution(returns: pd.Series) -> Panel:
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

    @staticmethod
    def render_capm_context(capm: Dict[str, Any], benchmark_ticker: str) -> Panel:
        points = capm.get("points") if isinstance(capm, dict) else None
        points_label = str(points) if points else "N/A"
        lines = [
            f"CAPM compares the portfolio to {benchmark_ticker} to estimate beta and alpha.",
            "Alpha is annualized excess return over CAPM expectations; beta is sensitivity to benchmark moves.",
            "R-squared shows how much of the return variance the benchmark explains.",
            f"Sample points: {points_label}; risk-free rate defaults to 4% annual unless configured.",
            "Short histories or regime shifts can make beta/alpha unstable; treat as descriptive.",
        ]
        return Panel("\n".join(lines), title="[bold]CAPM Context[/bold]", box=box.SIMPLE, border_style="dim")

    @staticmethod
    def render_risk_dashboard_context(interval: str, meta: str) -> Panel:
        lines = [
            f"Metrics use historical returns for the selected interval ({interval}).",
            "VaR/CVaR are historical tail summaries, not guaranteed loss limits.",
            "Return distribution buckets show frequency, not probability of future outcomes.",
            f"Data window: {meta}.",
        ]
        return Panel("\n".join(lines), title="[bold]Risk Dashboard Context[/bold]", box=box.SIMPLE, border_style="dim")

    @staticmethod
    def render_diagnostics_context(
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

    @staticmethod
    def render_black_scholes_context(
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
