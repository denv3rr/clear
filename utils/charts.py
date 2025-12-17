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
    def generate_bar(p: float, width: int = 20, color: str = "blue") -> Text:
        """
        Fixed-width probability bar. 
        Args:
            p: float 0.0 to 1.0
            width: total characters
            color: rich color style
        """
        try:
            v = float(p)
        except Exception:
            v = 0.0

        v = max(0.0, min(v, 1.0))
        
        filled = int(round(v * width))
        filled = max(0, min(filled, width))

        # Use full blocks + light blocks
        bar_text = ("█" * filled) + ("░" * (width - filled))
        return Text(bar_text, style=color)

    @staticmethod
    def generate_usage_bar(percent: float, width: int = 15) -> Text:
        """
        Specialized bar for system resource usage (0-100 scale).
        Color changes from Green -> Yellow -> Red based on severity.
        """
        # Determine Color based on severity
        if percent < 50:
            color = "green"
        elif percent < 80:
            color = "yellow"
        else:
            color = "bold red"
            
        # Normalize 0-100 to 0.0-1.0
        p = percent / 100.0
        return ChartRenderer.generate_bar(p, width, color)

    @staticmethod
    def regime_strip(regime_name: str, width: int = 28) -> Text:
        """Compact regime indicator strip."""
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
        
    @staticmethod
    def get_status_icon(active: bool) -> Text:
        """Returns a Check or X icon."""
        if active:
            return Text("✔", style="bold green")
        return Text("✘", style="bold red")