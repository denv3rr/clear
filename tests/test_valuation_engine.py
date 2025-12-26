import unittest
from datetime import datetime, timedelta

from modules.client_mgr.valuation import ValuationEngine


class TestValuationEngine(unittest.TestCase):
    def test_manual_holdings_value(self):
        engine = ValuationEngine()
        manual = [
            {"name": "Private Equity", "quantity": 2, "unit_price": 100.0},
            {"name": "Real Estate", "total_value": 250.0},
        ]
        total, normalized = engine.calculate_manual_holdings_value(manual)
        self.assertAlmostEqual(total, 450.0, places=6)
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["total_value"], 250.0)

    def test_lot_weighted_history_series(self):
        engine = ValuationEngine()
        start = datetime(2024, 1, 1, 10, 0, 0)
        dates = [start, start + timedelta(days=1)]
        enriched = {
            "AAPL": {
                "history": [100.0, 110.0],
                "history_dates": [d.strftime("%Y-%m-%dT%H:%M:%S") for d in dates],
                "quantity": 0.0,
            }
        }
        holdings = {"AAPL": 0.0}
        lot_map = {
            "AAPL": [
                {"qty": 1.0, "basis": 90.0, "timestamp": dates[0].strftime("%Y-%m-%dT%H:%M:%S")},
                {"qty": 1.0, "basis": 95.0, "timestamp": dates[1].strftime("%Y-%m-%dT%H:%M:%S")},
            ]
        }
        series_dates, values = engine.generate_portfolio_history_series(
            enriched_data=enriched,
            holdings=holdings,
            interval="1M",
            lot_map=lot_map,
        )
        self.assertEqual(len(series_dates), 2)
        self.assertEqual(values[0], 100.0)
        self.assertEqual(values[1], 220.0)


if __name__ == "__main__":
    unittest.main()
