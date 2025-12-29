import unittest

from modules.market_data.intel import (
    _aggregate_news_metrics,
    _impact_for_conflict,
    _impact_for_weather,
    _risk_level,
    _score_conflict,
    _score_weather,
)


class TestIntelScoring(unittest.TestCase):
    def test_risk_level_buckets(self):
        self.assertEqual(_risk_level(0), "Low")
        self.assertEqual(_risk_level(3), "Moderate")
        self.assertEqual(_risk_level(6), "High")
        self.assertEqual(_risk_level(9), "Severe")

    def test_score_weather_signals(self):
        score, signals = _score_weather(
            temp_c=36.0,
            wind_ms=20.0,
            precip_mm=12.0,
            precip_24h=30.0,
            wind_max=25.0,
            temp_min=5.0,
            temp_max=36.0,
        )
        self.assertGreaterEqual(score, 7)
        self.assertIn("Sustained high wind", signals)

    def test_score_conflict_signals(self):
        score, signals = _score_conflict(
            article_count=12,
            themes=["shipping", "energy", "military"],
        )
        self.assertGreaterEqual(score, 7)
        self.assertIn("Elevated conflict reporting", signals)

    def test_impact_for_weather(self):
        impacts = _impact_for_weather(temp_c=-12.0, wind_ms=16.0, precip_mm=15.0)
        self.assertTrue(any("logistics" in impact.lower() for impact in impacts))
        self.assertTrue(any("precipitation" in impact.lower() for impact in impacts))

    def test_impact_for_conflict(self):
        impacts = _impact_for_conflict(["oil", "shipping", "military"])
        self.assertTrue(any("energy" in impact.lower() for impact in impacts))
        self.assertTrue(any("shipping" in impact.lower() for impact in impacts))

    def test_news_aggregate_metrics(self):
        items = [
            {"title": "Markets surge on growth", "sentiment": 0.8, "tags": [], "categories": ["markets"], "emotions": {"optimism": 1}},
            {"title": "Conflict escalates after strike", "sentiment": -0.7, "tags": ["conflict"], "categories": ["conflict"], "emotions": {"fear": 2}},
            {"title": "Rates fall as inflation cools", "sentiment": 0.3, "tags": [], "categories": ["rates"], "emotions": {"anticipation": 1}},
        ]
        metrics = _aggregate_news_metrics(items)
        self.assertEqual(metrics["count"], 3)
        self.assertGreaterEqual(metrics["risk_score"], 0)
        self.assertIn("markets", metrics["category_counts"])


if __name__ == "__main__":
    unittest.main()
