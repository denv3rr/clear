import unittest

from modules.market_data.collectors import _dedupe_items, _parse_published_ts


class TestNewsCollectors(unittest.TestCase):
    def test_parse_published_ts_rfc822(self):
        ts = _parse_published_ts("Wed, 01 Jan 2025 10:00:00 GMT")
        self.assertIsNotNone(ts)
        self.assertGreater(ts, 0)

    def test_dedupe_items_keeps_newest(self):
        items = [
            {"title": "Market Update", "source": "Test", "url": "http://a", "published_ts": 100},
            {"title": "Market Update", "source": "Test", "url": "http://a", "published_ts": 200},
        ]
        deduped = _dedupe_items(items)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["published_ts"], 200)

    def test_dedupe_items_prefers_url(self):
        items = [
            {"title": "Macro Brief", "source": "Test", "url": "", "published_ts": 100},
            {"title": "Macro Brief", "source": "Test", "url": "http://b", "published_ts": 100},
        ]
        deduped = _dedupe_items(items)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["url"], "http://b")

    def test_dedupe_items_merges_same_url_across_sources(self):
        items = [
            {
                "title": "Oil routes remain under pressure",
                "summary": "Shipping lanes tightened after renewed strikes.",
                "source": "CNBC Top",
                "url": "https://www.cnbc.com/article?id=1&utm_source=rss",
                "published_ts": 100,
            },
            {
                "title": "Oil routes remain under pressure",
                "summary": "Shipping lanes tightened after renewed strikes.",
                "source": "CNBC World",
                "url": "https://www.cnbc.com/article?id=1",
                "published_ts": 101,
            },
        ]
        deduped = _dedupe_items(items)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(
            deduped[0]["canonical_url"],
            "https://www.cnbc.com/article?id=1",
        )
        self.assertEqual(deduped[0]["source"], "CNBC Top")
        self.assertEqual(deduped[0]["sources"], ["CNBC Top", "CNBC World"])
        self.assertEqual(deduped[0]["published_ts"], 101)

    def test_dedupe_items_merges_same_content_without_url(self):
        items = [
            {
                "title": "Iran conflict escalates",
                "summary": "Iran conflict escalates after overnight strikes near shipping lanes.",
                "source": "Feed A",
                "published_ts": 100,
            },
            {
                "title": "Iran conflict escalates",
                "summary": "Iran conflict escalates after overnight strikes near shipping lanes.",
                "source": "Feed B",
                "published_ts": 99,
            },
        ]
        deduped = _dedupe_items(items)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["sources"], ["Feed A", "Feed B"])


if __name__ == "__main__":
    unittest.main()
