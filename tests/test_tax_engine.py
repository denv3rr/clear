import tempfile
import unittest
from datetime import datetime, timedelta
import json

from modules.client_mgr.client_model import Account, Client
from modules.client_mgr.tax import TaxEngine


class TestTaxEngine(unittest.TestCase):
    def _build_rules_file(self):
        rules = {
            "DEFAULT": {
                "long_term_days": 365,
                "rates": {
                    "short_term": 30.0,
                    "long_term": 15.0,
                    "ordinary_income": None,
                    "withholding_default": None,
                },
                "apply_withholding_to_gains": False,
                "currency": "USD",
            }
        }
        tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="ascii")
        json.dump(rules, tmp)
        tmp.close()
        return tmp.name

    def test_estimate_account_unrealized_tax(self):
        rules_path = self._build_rules_file()
        engine = TaxEngine(rules_path=rules_path)
        account = Account(account_name="Test")
        long_ts = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%S")
        short_ts = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S")
        account.lots = {
            "AAPL": [
                {"qty": 10.0, "basis": 100.0, "timestamp": long_ts},
                {"qty": 5.0, "basis": 100.0, "timestamp": short_ts},
            ]
        }
        prices = {"AAPL": {"price": 120.0}}
        result = engine.estimate_account_unrealized_tax(account, prices, client_tax_profile={})
        self.assertAlmostEqual(result["total_unrealized"], 10 * 20 + 5 * 20, places=6)
        expected_tax = (10 * 20) * 0.15 + (5 * 20) * 0.30
        self.assertAlmostEqual(result["estimated_tax"], expected_tax, places=6)

    def test_tax_exempt_zeroes_tax(self):
        rules_path = self._build_rules_file()
        engine = TaxEngine(rules_path=rules_path)
        account = Account(account_name="Test")
        account.tax_settings["tax_exempt"] = True
        ts = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%S")
        account.lots = {"AAPL": [{"qty": 1.0, "basis": 100.0, "timestamp": ts}]}
        prices = {"AAPL": {"price": 120.0}}
        result = engine.estimate_account_unrealized_tax(account, prices, client_tax_profile={})
        self.assertEqual(result["estimated_tax"], 0.0)

    def test_estimate_client_unrealized_tax(self):
        rules_path = self._build_rules_file()
        engine = TaxEngine(rules_path=rules_path)
        client = Client(name="Test")
        account = Account(account_name="Test")
        ts = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%S")
        account.lots = {"AAPL": [{"qty": 2.0, "basis": 100.0, "timestamp": ts}]}
        client.accounts.append(account)
        prices = {"AAPL": {"price": 120.0}}
        result = engine.estimate_client_unrealized_tax(client, prices)
        self.assertAlmostEqual(result["total_unrealized"], 40.0, places=6)


if __name__ == "__main__":
    unittest.main()
