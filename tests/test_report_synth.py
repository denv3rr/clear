import os
import tempfile
import unittest

from utils.report_synth import ReportContext, ReportSynthesizer, analyze_news_items


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


if __name__ == "__main__":
    unittest.main()
