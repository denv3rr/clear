import unittest

from modules.market_data.trackers import GlobalTrackers, TrackerRelevance


class TestTrackersMetrics(unittest.TestCase):
    def test_stddev_min_points(self):
        self.assertIsNone(GlobalTrackers._stddev([1.0, 2.0, 3.0]))
        std = GlobalTrackers._stddev([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(std, 1.1180, places=3)

    def test_heat_from_value(self):
        self.assertIsNone(GlobalTrackers._heat_from_value(None, 10.0))
        self.assertEqual(GlobalTrackers._heat_from_value(5.0, 10.0), 0.5)
        self.assertEqual(GlobalTrackers._heat_from_value(20.0, 10.0), 1.0)

    def test_summarize_points(self):
        points = [
            {"speed_kts": 10.0, "speed_vol_kts": 1.0, "speed_heat": 0.2, "vol_heat": 0.1},
            {"speed_kts": 20.0, "speed_vol_kts": 3.0, "speed_heat": 0.4, "vol_heat": 0.3},
        ]
        summary = TrackerRelevance.summarize(points)
        self.assertEqual(summary["point_count"], 2)
        self.assertAlmostEqual(summary["avg_speed_kts"], 15.0, places=6)
        self.assertAlmostEqual(summary["avg_vol_kts"], 2.0, places=6)
        self.assertEqual(summary["max_speed_kts"], 20.0)


if __name__ == "__main__":
    unittest.main()
