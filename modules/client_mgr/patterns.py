from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from modules.client_mgr import calculations
from utils.charts import ChartRenderer


class PatternSuite:
    def __init__(self, perm_entropy_order: int = 3, perm_entropy_delay: int = 1) -> None:
        self.perm_entropy_order = perm_entropy_order
        self.perm_entropy_delay = perm_entropy_delay

    def build_payload(self, returns: pd.Series, interval: str, meta: str) -> Dict[str, Any]:
        values = self.returns_to_values(returns)
        spectrum = calculations.fft_spectrum(values, top_n=6)
        change_points = calculations.cusum_change_points(returns, threshold=5.0)
        motifs = calculations.motif_similarity(returns, window=20, top=3)
        vol_forecast = calculations.ewma_vol_forecast(returns, lam=0.94, steps=6)
        entropy = calculations.shannon_entropy(returns, bins=12)
        perm_entropy = calculations.permutation_entropy(
            values,
            order=self.perm_entropy_order,
            delay=self.perm_entropy_delay,
        )
        hurst = calculations.hurst_exponent(values)

        return {
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

    @staticmethod
    def returns_to_values(returns: pd.Series) -> List[float]:
        vals = [1.0]
        for r in returns:
            vals.append(vals[-1] * (1.0 + float(r)))
        return vals[1:]

    @staticmethod
    def build_surfaces(values: List[float]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        return PatternSuite._wave_surface(values), PatternSuite._fft_surface(values)

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


class PatternRenderer:
    @staticmethod
    def render_pattern_summary(payload: Dict[str, Any]) -> Table:
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

    @staticmethod
    def render_spectrum_panel(payload: Dict[str, Any]) -> Panel:
        values = payload["values"]
        waveform = PatternRenderer.render_waveform(values, width=60, height=10)

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

    @staticmethod
    def render_changepoint_panel(payload: Dict[str, Any]) -> Panel:
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

    @staticmethod
    def render_motif_panel(payload: Dict[str, Any]) -> Panel:
        motifs = payload["motifs"]
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Window", style="bold cyan")
        table.add_column("Distance", justify="right")
        for match in motifs:
            table.add_row(match["window"], f"{match['distance']:.3f}")
        if not motifs:
            table.add_row("N/A", "Insufficient history")
        return Panel(table, title="Motif Similarity", box=box.ROUNDED, border_style="magenta")

    @staticmethod
    def render_vol_forecast_panel(payload: Dict[str, Any]) -> Panel:
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

    @staticmethod
    def render_entropy_panel(payload: Dict[str, Any]) -> Panel:
        summary = PatternRenderer.render_pattern_summary(payload)
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
    def render_waveform(values: List[float], width: int = 60, height: int = 10) -> Text:
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
