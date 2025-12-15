from rich.text import Text

class ChartRenderer:
    """
    Utility for generating text-based visualizations (Sparklines, Trend Arrows).
    """

    @staticmethod
    def generate_sparkline(data: list, length: int = 20, color_trend: bool = True) -> Text:
        """
        Converts a list of numerical values into a sparkline string.
        """
        if not data or len(data) < 2:
            return Text("─" * length, style="dim")
        
        # Slice data to fit desired length
        display_data = data[-length:] if len(data) > length else data

        bars = u" ▂▃▄▅▆▇█"
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

        # Color logic: Green if ending higher than start, else Red
        style = "white"
        if color_trend:
            style = "bold green" if display_data[-1] >= display_data[0] else "bold red"
            
        return Text(sparkline_str, style=style)

    @staticmethod
    def get_trend_arrow(change: float) -> Text:
        """Returns a colored trend arrow."""
        if change > 0:
            return Text("▲", style="bold green")
        elif change < 0:
            return Text("▼", style="bold red")
        else:
            return Text("▶", style="dim white")