import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from modules.market_data.intel import (
    MarketIntel,
    _filter_conflict_news,
    _aliases_path_from_settings,
    get_ticker_aliases,
    load_ticker_aliases,
    news_cache_status,
    score_news_item,
    score_news_items,
    validate_alias_file,
)


class TestIntelNewsFilters(unittest.TestCase):
    def setUp(self):
        self.intel = MarketIntel()

    def test_filter_news_region_and_industry(self):
        items = [
            {"title": "Energy shock hits Europe", "regions": ["Europe"], "industries": ["energy"]},
            {"title": "Agriculture exports rise", "regions": ["Latin America"], "industries": ["agriculture"]},
            {"title": "Global tech policy update", "regions": ["Global"], "industries": ["tech"]},
        ]
        filtered = self.intel._filter_news(items, "Europe", "energy")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["title"], "Energy shock hits Europe")

    def test_filter_conflict_news_categories(self):
        items = [
            {"title": "Shipping lanes disrupted after strike", "tags": ["conflict"], "regions": ["Europe"]},
            {"title": "Oil infrastructure attacked amid tensions", "industries": ["energy"], "regions": ["Europe"]},
            {"title": "Tech earnings beat estimates", "tags": ["finance"], "regions": ["Europe"]},
        ]
        filtered = _filter_conflict_news(items, "Europe", categories=["conflict", "energy"])
        titles = {item["title"] for item in filtered}
        self.assertIn("Shipping lanes disrupted after strike", titles)
        self.assertIn("Oil infrastructure attacked amid tensions", titles)
        self.assertNotIn("Tech earnings beat estimates", titles)

    def test_score_news_item_relevance(self):
        now = int(time.time())
        match = {
            "title": "AAPL reports earnings beat",
            "regions": ["North America"],
            "industries": ["tech"],
            "tags": ["finance"],
            "published_ts": now,
        }
        miss = {
            "title": "Copper output rises",
            "regions": ["Latin America"],
            "industries": ["mining"],
            "published_ts": now - 100000,
        }
        score_match = score_news_item(match, tickers=["AAPL"], region="North America", industry="tech")
        score_miss = score_news_item(miss, tickers=["AAPL"], region="North America", industry="tech")
        self.assertGreaterEqual(score_match, 10)
        self.assertLess(score_miss, score_match)

    def test_score_news_item_matches_alias(self):
        now = int(time.time())
        item = {
            "title": "Apple announces new chip lineup",
            "regions": ["North America"],
            "industries": ["tech"],
            "published_ts": now,
        }
        score = score_news_item(item, tickers=["AAPL"], region="North America", industry="tech")
        self.assertGreaterEqual(score, 8)

    def test_score_news_item_matches_etf_alias(self):
        item = {"title": "S&P 500 slips as yields rise"}
        score = score_news_item(item, tickers=["SPY"])
        self.assertGreaterEqual(score, 6)

    def test_score_news_items_orders_by_recency(self):
        now = int(time.time())
        items = [
            {"title": "AAPL update", "published_ts": now - 3600},
            {"title": "AAPL update older", "published_ts": now - 100000},
        ]
        scored = score_news_items(items, tickers=["AAPL"])
        self.assertEqual(scored[0][1]["title"], "AAPL update")

    def test_fetch_news_signals_falls_back_to_stale(self):
        intel = MarketIntel()
        with patch("modules.market_data.intel.fetch_news_items") as fetch, patch(
            "modules.market_data.intel.load_cached_news"
        ) as load:
            fetch.return_value = {"items": [], "skipped": [], "health": {}}
            load.return_value = [{"title": "Cached item", "source": "Test"}]
            result = intel.fetch_news_signals(ttl_seconds=0, force=True)
            self.assertTrue(result["cached"])
            self.assertTrue(result["stale"])
            self.assertEqual(result["items"][0]["title"], "Cached item")

    def test_news_cache_status(self):
        self.assertEqual(news_cache_status(None), "unknown")
        self.assertEqual(news_cache_status({"items": []}), "empty")
        self.assertEqual(news_cache_status({"items": [{"title": "x"}]}), "fresh")
        self.assertEqual(news_cache_status({"items": [{"title": "x"}], "stale": True}), "stale")

    def test_load_ticker_aliases_from_file(self):
        payload = {"ABCD": ["Example Corp", "Example Inc"]}
        with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", delete=False) as handle:
            json.dump(payload, handle)
            path = handle.name
        try:
            aliases = load_ticker_aliases(path)
            self.assertIn("ABCD", aliases)
            self.assertIn("Example Corp", aliases["ABCD"])
        finally:
            os.unlink(path)

    def test_get_ticker_aliases_uses_custom_file(self):
        payload = {"WXYZ": ["Widget Corp"]}
        with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", delete=False) as handle:
            json.dump(payload, handle)
            path = handle.name
        try:
            aliases = get_ticker_aliases(path=path)
            item = {"title": "Widget Corp announces merger"}
            score = score_news_item(item, tickers=["WXYZ"], ticker_aliases=aliases)
            self.assertGreaterEqual(score, 6)
        finally:
            os.unlink(path)

    def test_aliases_path_from_settings(self):
        payload = {"news": {"aliases_file": "config/custom_aliases.json"}}
        with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", delete=False) as handle:
            json.dump(payload, handle)
            path = handle.name
        try:
            resolved = _aliases_path_from_settings(path)
            expected = os.path.normpath(os.path.join(os.getcwd(), "config", "custom_aliases.json"))
            self.assertEqual(resolved, expected)
        finally:
            os.unlink(path)

    def test_validate_alias_file(self):
        payload = {"ABCD": ["Example Corp", "Example Inc"]}
        with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", delete=False) as handle:
            json.dump(payload, handle)
            path = handle.name
        try:
            ok, message = validate_alias_file(path)
            self.assertTrue(ok)
            self.assertEqual(message, "ok")
        finally:
            os.unlink(path)

    def test_validate_alias_file_rejects_bad(self):
        payload = ["bad"]
        with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", delete=False) as handle:
            json.dump(payload, handle)
            path = handle.name
        try:
            ok, message = validate_alias_file(path)
            self.assertFalse(ok)
            self.assertIn("JSON object", message)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
