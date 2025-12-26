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


if __name__ == "__main__":
    unittest.main()
