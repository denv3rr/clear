import unittest

from modules.market_data.intel import MarketIntel, _filter_conflict_news


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


if __name__ == "__main__":
    unittest.main()
