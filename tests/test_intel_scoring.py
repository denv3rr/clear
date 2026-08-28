import unittest
from unittest import mock

from modules.market_data.intel import (
    REGION_CONFLICT_QUERY_TERMS,
    MarketIntel,
    REGIONS,
    WeatherIntel,
    _aggregate_news_metrics,
    _impact_for_conflict,
    _impact_for_weather,
    rank_news_items,
    _risk_level,
    _score_conflict,
    _score_weather,
    score_news_item,
)


class TestIntelScoring(unittest.TestCase):
    def test_weather_fetch_failure_does_not_expose_exception_detail(self):
        with mock.patch(
            "modules.market_data.intel.requests.get",
            side_effect=RuntimeError("PRIVATE_WEATHER_SENTINEL"),
        ):
            payload = WeatherIntel().fetch(REGIONS[0])

        self.assertEqual(payload["error"], "Open-Meteo fetch failed.")
        self.assertNotIn("PRIVATE_WEATHER_SENTINEL", payload["error"])

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
        impacts = _impact_for_weather(
            temp_c=-12.0,
            wind_ms=16.0,
            precip_mm=15.0,
            precip_24h=28.0,
            wind_max=19.0,
            temp_min=-14.0,
            temp_max=34.0,
        )
        self.assertTrue(any("logistics" in impact.lower() for impact in impacts))
        self.assertTrue(any("flood" in impact.lower() for impact in impacts))
        self.assertTrue(any("wildfire" in impact.lower() for impact in impacts))

    def test_impact_for_conflict(self):
        impacts = _impact_for_conflict(["oil", "shipping", "military"])
        self.assertTrue(any("energy" in impact.lower() for impact in impacts))
        self.assertTrue(any("shipping" in impact.lower() for impact in impacts))

    def test_news_aggregate_metrics(self):
        items = [
            {
                "title": "Markets surge on growth",
                "sentiment": 0.8,
                "tags": [],
                "categories": ["markets"],
                "impact_channels": ["finance_insurance"],
                "emotions": {"optimism": 1},
                "regions": ["North America"],
                "industries": ["finance"],
            },
            {
                "title": "Conflict escalates after strike",
                "sentiment": -0.7,
                "event_tags": ["conflict", "disruption"],
                "categories": ["conflict"],
                "impact_channels": ["shipping_logistics", "energy"],
                "emotions": {"fear": 2},
                "regions": ["Europe"],
                "industries": ["shipping"],
            },
            {
                "title": "Rates fall as inflation cools",
                "sentiment": 0.3,
                "tags": [],
                "categories": ["rates"],
                "impact_channels": ["finance_insurance"],
                "emotions": {"anticipation": 1},
                "regions": ["North America"],
                "industries": ["finance"],
            },
        ]
        metrics = _aggregate_news_metrics(items)
        self.assertEqual(metrics["count"], 3)
        self.assertGreaterEqual(metrics["risk_score"], 0)
        self.assertIn("markets", metrics["category_counts"])
        self.assertEqual(metrics["event_counts"]["conflict"], 1)
        self.assertEqual(metrics["impact_counts"]["finance_insurance"], 2)
        self.assertIn("Europe", metrics["region_emotion_counts"])
        self.assertIn("finance", metrics["industry_emotion_counts"])

    def test_news_metrics_empty_series(self):
        metrics = _aggregate_news_metrics([])
        self.assertEqual(metrics["count"], 0)
        self.assertEqual(metrics["series"], [])
        self.assertEqual(metrics["emotion_series"], [])

    def test_conflict_query_terms_cover_reported_active_regions(self):
        self.assertIn("Myanmar", REGION_CONFLICT_QUERY_TERMS["Asia-Pacific"])
        self.assertIn("People's Defense Force", REGION_CONFLICT_QUERY_TERMS["Asia-Pacific"])
        self.assertIn("Ukraine", REGION_CONFLICT_QUERY_TERMS["Europe"])
        self.assertIn("Gaza", REGION_CONFLICT_QUERY_TERMS["Middle East"])
        self.assertIn("Congo", REGION_CONFLICT_QUERY_TERMS["Africa"])

    def test_conflict_news_ranks_ahead_of_same_region_general_news(self):
        items = [
            {
                "title": "Asia-Pacific factories report stable exports",
                "regions": ["Asia-Pacific"],
                "industries": ["manufacturing"],
                "tags": ["supply-chain"],
                "categories": ["macro"],
            },
            {
                "title": "Myanmar junta airstrike intensifies conflict with resistance forces",
                "regions": ["Asia-Pacific"],
                "industries": ["shipping"],
                "tags": ["conflict"],
                "event_tags": ["conflict", "airstrike"],
                "categories": ["conflict"],
            },
        ]
        ranked = rank_news_items(items, region="Asia-Pacific")
        self.assertEqual(ranked[0]["title"], items[1]["title"])

    def test_conflict_priority_accepts_single_string_categories(self):
        score = score_news_item(
            {
                "title": "Myanmar junta shelling disrupts regional logistics",
                "regions": "Asia-Pacific",
                "industries": "shipping",
                "categories": "conflict",
                "event_tags": "airstrike",
                "tags": "conflict",
            },
            region="Asia-Pacific",
            industry="shipping",
        )
        self.assertGreaterEqual(score, 7)

    def test_combined_report_omits_series_without_news(self):
        intel = MarketIntel()
        weather_stub = {
            "risk_score": 4,
            "risk_level": "Moderate",
            "confidence": None,
            "support": {"summary": "3/3 weather inputs available", "available_inputs": 3},
            "signals": [],
            "impacts": [],
            "sections": [],
        }
        conflict_stub = {
            "risk_score": 5,
            "risk_level": "Moderate",
            "confidence": None,
            "support": {"summary": "9 supporting articles", "article_count": 9},
            "signals": [],
            "impacts": [],
            "sections": [],
        }
        with mock.patch.object(intel, "fetch_news_signals", return_value={"items": []}), mock.patch.object(
            intel, "weather_report", return_value=weather_stub
        ), mock.patch.object(intel, "conflict_report", return_value=conflict_stub):
            report = intel.combined_report("Global")
        self.assertEqual(report["risk_series"], [])


if __name__ == "__main__":
    unittest.main()
