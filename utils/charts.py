from rich.text import Text


class ChartRenderer:
    """
    Utility for generating text-based visualizations (Sparklines, Bars, Regime strips).
    """

    @staticmethod
    def generate_sparkline(data: list, length: int = 20, color_trend: bool = True) -> Text:
        """
        Converts a list of numerical values into a sparkline Text.
        """
        if not data or len(data) < 2:
            return Text("─" * length, style="dim")

        display_data = data[-length:] if len(data) > length else data

        bars = " ▂▃▄▅▆▇█"
        min_val = min(display_data)
        max_val = max(display_data)
        spread = max_val - min_val

        sparkline_str = ""
        if spread == 0:
            sparkline_str = "─" * len(display_data)
        else:
            for val in display_data:
                norm = (val - min_val) / spread
                idx = int(norm * (len(bars) - 1))
                sparkline_str += bars[idx]

        style = "white"
        if color_trend:
            style = "bold green" if display_data[-1] >= display_data[0] else "bold red"

        return Text(sparkline_str, style=style)

    @staticmethod
    def generate_bar(p: float, width: int = 20) -> Text:
        """
        Fixed-width probability bar that will not render with Rich's ellipsis truncation.
        """
        try:
            v = float(p)
        except Exception:
            v = 0.0

        if v < 0.0:
            v = 0.0
        if v > 1.0:
            v = 1.0

        filled = int(round(v * width))
        if filled < 0:
            filled = 0
        if filled > width:
            filled = width

        # Use full blocks + light blocks for stable monospace rendering
        return Text(("█" * filled) + ("░" * (width - filled)))

    @staticmethod
    def regime_strip(regime_name: str, width: int = 28) -> Text:
        """
        Compact regime indicator strip (color-coded) that can sit above/beside the regime panel.
        """
        name = (regime_name or "").lower()
        style = "dim"

        if "strong up" in name:
            style = "bold green"
        elif "mild up" in name:
            style = "green"
        elif "flat" in name:
            style = "bold yellow"
        elif "mild down" in name:
            style = "red"
        elif "strong down" in name:
            style = "bold red"

        return Text("▮" * width, style=style)

    @staticmethod
    def get_trend_arrow(change: float) -> Text:
        """Returns a colored trend arrow."""
        if change > 0:
            return Text("▲", style="bold green")
        if change < 0:
            return Text("▼", style="bold red")
        return Text("▶", style="dim white")
