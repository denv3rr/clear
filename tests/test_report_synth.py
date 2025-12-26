import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from utils.report_synth import (
    ReportContext,
    ReportSynthesizer,
    analyze_news_items,
    build_ai_sections,
    filter_fresh_news_items,
)


class TestReportSynth(unittest.TestCase):
    def test_analyze_news_items_emotion_bias(self):
        items = [
            {"title": "Reportedly shocking crisis rattles markets", "source": "Demo"},
        ]
        analysis = analyze_news_items(items)
        agg = analysis.get("aggregate", {})
        self.assertGreater(agg.get("article_count", 0), 0)
        self.assertIn("reportedly", agg.get("bias_markers", []))
        self.assertIn("shocking", agg.get("sensationalism_markers", []))

    def test_cache_hit_on_repeat(self):
        context = ReportContext(
            report_type="combined",
            region="Europe",
            industry="energy",
            summary=["Region: Europe"],
            risk_level="High",
            risk_score=7,
            confidence="Medium",
            signals=["Elevated conflict reporting"],
            impacts=["Energy supply risks elevated."],
            sections=[],
            news_items=[],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "cache.json")
            synth = ReportSynthesizer(cache_file=cache_path, cache_ttl=3600)
            first = synth.synthesize(context)
            second = synth.synthesize(context)
            self.assertFalse(first.get("cache", {}).get("hit", True))
            self.assertTrue(second.get("cache", {}).get("hit", False))

    def test_filter_fresh_news_items(self):
        now = int(time.time())
        items = [
            {"title": "Fresh", "published_ts": now - 60},
            {"title": "Stale", "published_ts": now - 3600 * 48},
        ]
        fresh = filter_fresh_news_items(items, max_age_hours=24)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh[0]["title"], "Fresh")

    def test_news_analysis_uses_fresh_only(self):
        now = int(time.time())
        context = ReportContext(
            report_type="combined",
            region="Europe",
            industry="energy",
            summary=["Region: Europe"],
            risk_level="High",
            risk_score=7,
            confidence="Medium",
            signals=["Elevated conflict reporting"],
            impacts=["Energy supply risks elevated."],
            sections=[],
            news_items=[
                {"title": "Fresh news", "published_ts": now - 300},
                {"title": "Old news", "published_ts": now - 3600 * 72},
            ],
        )
        synth = ReportSynthesizer(
            cache_file=os.path.join(tempfile.gettempdir(), "cache.json"),
            cache_ttl=0,
            news_freshness_hours=24,
        )
        result = synth.synthesize(context)
        analysis = result.get("analysis", {})
        self.assertEqual(analysis.get("fresh_article_count"), 1)
        self.assertEqual(analysis.get("stale_filtered"), 1)

    def test_news_freshness_default_from_settings(self):
        payload = {"ai": {"news_freshness_hours": 2}}
        context = ReportContext(
            report_type="combined",
            region="Europe",
            industry="energy",
            summary=["Region: Europe"],
            risk_level="High",
            risk_score=7,
            confidence="Medium",
            signals=["Elevated conflict reporting"],
            impacts=["Energy supply risks elevated."],
            sections=[],
            news_items=[],
        )
        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(payload))), \
            patch("os.path.exists") as exists:
            exists.return_value = True
            synth = ReportSynthesizer(cache_file=os.path.join(tempfile.gettempdir(), "cache.json"), cache_ttl=0)
            self.assertEqual(synth.news_freshness_hours, 2)

    def test_build_ai_sections_includes_freshness(self):
        payload = {
            "analysis": {
                "aggregate": {"emotion_density": {}},
                "fresh_article_count": 2,
                "stale_filtered": 1,
            }
        }
        sections = build_ai_sections(payload)
        self.assertTrue(sections)
        rows = sections[0].get("rows", [])
        self.assertIn(["Fresh Articles", "2"], rows)
        self.assertIn(["Stale Filtered", "1"], rows)

    def test_auto_provider_uses_local_http_when_available(self):
        context = ReportContext(
            report_type="combined",
            region="Europe",
            industry="energy",
            summary=["Region: Europe"],
            risk_level="High",
            risk_score=7,
            confidence="Medium",
            signals=["Elevated conflict reporting"],
            impacts=["Energy supply risks elevated."],
            sections=[],
            news_items=[],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "cache.json")
            synth = ReportSynthesizer(
                provider="auto",
                model_id="llama3",
                endpoint="http://127.0.0.1:8080",
                cache_file=cache_path,
                cache_ttl=3600,
            )
            with patch("utils.report_synth._try_local_llm") as local_llm:
                local_llm.return_value = {"outlook": "OK", "notes": []}
                result = synth.synthesize(context)
                self.assertEqual(result.get("provider"), "local_http")
                self.assertEqual(result.get("model_id"), "llama3")


if __name__ == "__main__":
    unittest.main()
