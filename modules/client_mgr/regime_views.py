from __future__ import annotations

from typing import Any

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
                border_style="yellow",
            )

        # --- LEFT: summary ---
        left = Table.grid(padding=(0, 2))
        left.add_column(style="dim")
        left.add_column(justify="right", style="bold white")

        left.add_row()
        left.add_row(
            "State",
            ChartRenderer.regime_strip(snapshot["current_regime"], width=10),
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
            RegimeRenderer._fmt_pct(snapshot["metrics"]["avg_return"]),
        )
        left.add_row(
            "Volatility (Ann.)",
            RegimeRenderer._fmt_pct(snapshot["metrics"]["volatility"]),
        )

        # --- RIGHT: regime probabilities ---
        prob_table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style="bold",
            expand=False,
            width=50,
        )
        prob_table.add_column("Regime", style="bold cyan")
        prob_table.add_column("Prob", justify="right")
        prob_table.add_column("Heat")

        probs = snapshot.get("state_probs", {})
        if probs:
            for k, v in probs.items():
                prob = float(v or 0.0)
                bar = ChartRenderer.generate_heatmap_bar(prob, width=18)
                prob_table.add_row(str(k), RegimeRenderer._fmt_pct(prob), bar)
        else:
            prob_table.add_row("N/A", "N/A", "")

        right = Panel(prob_table, title="Regime Probabilities", box=box.ROUNDED)

        layout = Table.grid(expand=True)
        layout.add_column(ratio=1)
        layout.add_column(ratio=1)
        layout.add_row(Panel(left, title="Snapshot", box=box.ROUNDED), right)

        # --- TRANSITION MATRIX + SURFACES ---
        stack = []
        if snapshot.get("transition_matrix"):
            matrix = RegimeRenderer._render_transition_heatmap(
                snapshot["transition_matrix"], snapshot["states"],
            )
            stack.append(
                Panel(
                    matrix,
                    title="[bold]Transition Heatmap[/bold]",
                    box=box.ROUNDED,
                )
            )

        if snapshot.get("transition_matrix"):
            trans_surf = RegimeRenderer._render_transition_surface(snapshot["transition_matrix"])
            stack.append(
                Panel(
                    trans_surf,
                    title="[bold]Transition Surface[/bold]",
                    box=box.ROUNDED,
                )
            )

        if snapshot.get("stationary"):
            stat_surf = RegimeRenderer._render_stationary_surface(snapshot["stationary"])
            stack.append(
                Panel(
                    stat_surf,
                    title="[bold]Stationary Distribution[/bold]",
                    box=box.ROUNDED,
                )
            )

        if snapshot.get("evolution"):
            labels = snapshot.get("states", [])
            evo_surf = RegimeRenderer._render_evolution_surface(snapshot["evolution"], labels)
            stack.append(
                Panel(
                    evo_surf,
                    title="[bold]Regime Evolution[/bold]",
                    box=box.ROUNDED,
                )
            )

        surfaces_group = None
        if stack:
            surfaces_group = Group(*stack)

        if surfaces_group is not None:
            stack.append(
                Panel(
                    surfaces_group,
                    title="[bold]Surfaces[/bold]",
                    box=box.ROUNDED,
                )
            )
        else:
            stack.append(
                Panel(
                    "[dim]Surface data not available.[/dim]",
                    title="[bold]Surfaces[/bold]",
                    box=box.ROUNDED,
                )
            )

        final = Group(layout, *stack)

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
            box=box.HEAVY,
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

            if p >= 0.95:
                ch, col = "█", "bold red"
            elif p >= 0.85:
                ch, col = "▇", "red"
            elif p >= 0.70:
                ch, col = "▆", "yellow"
            elif p >= 0.55:
                ch, col = "▅", "green"
            elif p >= 0.40:
                ch, col = "▄", "cyan"
            elif p >= 0.25:
                ch, col = "▃", "blue"
            elif p >= 0.10:
                ch, col = "▂", "dim cyan"
            else:
                ch, col = "▁", "dim white"

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
        tab.add_column("pi", justify="right", width=7)
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
            if p_val >= 0.90:
                ch, col = "█", "bold red"
            elif p_val >= 0.70:
                ch, col = "█", "red"
            elif p_val >= 0.50:
                ch, col = "▓", "yellow"
            elif p_val >= 0.40:
                ch, col = "▒", "green"
            elif p_val >= 0.20:
                ch, col = "░", "blue"
            elif p_val >= 0.10:
                ch, col = "░", "cyan"
            else:
                ch, col = "·", "white"

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
