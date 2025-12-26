import unittest

from utils.charts import ChartRenderer


class TestChartRenderer(unittest.TestCase):
    def test_generate_sparkline_constant(self):
        text = ChartRenderer.generate_sparkline([1, 1, 1, 1], length=4)
        self.assertEqual(text.plain, "────")

    def test_generate_bar_half(self):
        text = ChartRenderer.generate_bar(0.5, width=10)
        self.assertEqual(len(text.plain), 10)
        self.assertEqual(text.plain.count("█"), 5)

    def test_generate_heatmap_bar_bounds(self):
        low = ChartRenderer.generate_heatmap_bar(-1.0, width=5)
        high = ChartRenderer.generate_heatmap_bar(2.0, width=5)
        self.assertEqual(len(low.plain), 5)
        self.assertEqual(len(high.plain), 5)

    def test_trend_arrow(self):
        up = ChartRenderer.get_trend_arrow(1.0)
        down = ChartRenderer.get_trend_arrow(-1.0)
        flat = ChartRenderer.get_trend_arrow(0.0)
        self.assertEqual(up.plain, "▲")
        self.assertEqual(down.plain, "▼")
        self.assertEqual(flat.plain, "▶")


if __name__ == "__main__":
    unittest.main()
