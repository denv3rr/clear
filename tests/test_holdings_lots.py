import json
import unittest
from datetime import datetime, timedelta

from interfaces.components import UIComponents
from modules.client_mgr.client_model import Account
from modules.client_mgr.holdings import (
    build_lot_entry,
    compute_weighted_avg_cost,
    select_nearest_price,
)


def _cell_text(cell) -> str:
    if hasattr(cell, "plain"):
        return cell.plain
    return str(cell)


class TestHoldingsLots(unittest.TestCase):
    def test_weighted_avg_cost(self):
        lots = [
            {"qty": 10.0, "basis": 100.0},
            {"qty": 5.0, "basis": 110.0},
        ]
        avg = compute_weighted_avg_cost(lots)
        self.assertAlmostEqual(avg, (10 * 100 + 5 * 110) / 15, places=6)

    def test_weighted_avg_with_aggregate(self):
        lots = [
            {"qty": 4.0, "basis": 50.0, "kind": "aggregate"},
            {"qty": 1.5, "basis": 80.0, "kind": "lot"},
        ]
        avg = compute_weighted_avg_cost(lots)
        expected = (4.0 * 50.0 + 1.5 * 80.0) / 5.5
        self.assertAlmostEqual(avg, expected, places=6)

    def test_build_lot_entry_respects_manual_basis(self):
        ts = datetime(2023, 11, 10, 14, 30, 0)
        entry = build_lot_entry(
            qty=3.0,
            basis=42.0,
            timestamp=ts,
            source="CUSTOM",
            price_lookup=lambda _: 99.0,
        )
        self.assertEqual(entry["basis"], 42.0)
        self.assertIn("2023-11-10T14:30:00", entry["timestamp"])

    def test_build_lot_entry_uses_price_lookup_when_missing_basis(self):
        ts = datetime(2022, 1, 2, 3, 4, 5)
        entry = build_lot_entry(
            qty=1.0,
            basis=None,
            timestamp=ts,
            source="HISTORICAL",
            price_lookup=lambda _: 123.45,
        )
        self.assertAlmostEqual(entry["basis"], 123.45, places=6)

    def test_build_lot_entry_missing_basis_without_lookup_raises(self):
        ts = datetime(2022, 1, 2, 3, 4, 5)
        with self.assertRaises(ValueError):
            build_lot_entry(qty=1.0, basis=None, timestamp=ts, source="HISTORICAL")

    def test_select_nearest_price(self):
        base = datetime(2024, 1, 1, 10, 0, 0)
        series = [
            (base, 100.0),
            (base + timedelta(minutes=10), 105.0),
            (base + timedelta(minutes=20), 110.0),
        ]
        target = base + timedelta(minutes=12)
        price = select_nearest_price(series, target)
        self.assertEqual(price, 105.0)

    def test_persistence_round_trip_preserves_lots(self):
        acct = Account(
            account_id="acct-1",
            account_name="Test",
            account_type="Taxable",
        )
        acct.lots = {
            "AAPL": [
                {
                    "qty": 2.5,
                    "basis": 150.0,
                    "timestamp": "2023-11-10T14:30:00",
                    "source": "CUSTOM",
                    "kind": "lot",
                },
                {
                    "qty": 1.0,
                    "basis": 120.0,
                    "timestamp": "AGGREGATE",
                    "source": "AGGREGATE",
                    "kind": "aggregate",
                },
            ]
        }
        acct.sync_holdings_from_lots()
        payload = json.loads(json.dumps(acct.to_dict()))
        reloaded = Account.from_dict(payload)
        self.assertIn("AAPL", reloaded.lots)
        self.assertEqual(len(reloaded.lots["AAPL"]), 2)
        self.assertAlmostEqual(reloaded.holdings["AAPL"], 3.5, places=6)
        ts = reloaded.lots["AAPL"][0].get("timestamp")
        self.assertEqual(ts, "2023-11-10T14:30:00")

    def test_holdings_table_lots_under_parent(self):
        acct = Account(account_id="acct-2", account_name="Test")
        acct.holdings = {"AAPL": 3.0}
        acct.lots = {
            "AAPL": [
                {"qty": 2.0, "basis": 100.0, "timestamp": "2023-01-01T10:00:00"},
                {"qty": 1.0, "basis": 110.0, "timestamp": "2023-02-01T10:00:00"},
            ]
        }
        enriched = {
            "AAPL": {
                "price": 130.0,
                "market_value": 390.0,
                "change_pct": 1.0,
            }
        }
        table = UIComponents.holdings_table(acct, enriched, total_val=390.0)
        first_col = table.columns[0]._cells
        price_col = table.columns[3]._cells
        self.assertGreaterEqual(len(first_col), 2)
        self.assertEqual(_cell_text(first_col[0]), "AAPL")
        self.assertIn("Lot", _cell_text(first_col[1]))
        lot_price = _cell_text(price_col[1])
        self.assertIn("100.00", lot_price)


if __name__ == "__main__":
    unittest.main()
