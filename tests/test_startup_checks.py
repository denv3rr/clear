import unittest

from run import _validate_clients_payload


class TestStartupChecks(unittest.TestCase):
    def test_validate_clients_payload_ok(self):
        payload = [
            {
                "client_id": "c1",
                "name": "Client",
                "accounts": [
                    {
                        "account_id": "a1",
                        "account_name": "Brokerage",
                        "holdings": {"AAPL": 1.5},
                        "lots": {"AAPL": [{"qty": 1.5, "basis": 100.0, "timestamp": "2024-01-01T10:00:00"}]},
                        "manual_holdings": [],
                    }
                ],
            }
        ]
        errors = _validate_clients_payload(payload)
        self.assertEqual(errors, [])

    def test_validate_clients_payload_invalid(self):
        payload = [
            {"name": "Missing ID", "accounts": "bad"},
        ]
        errors = _validate_clients_payload(payload)
        self.assertTrue(errors)
        self.assertIn("missing client_id or name", " ".join(errors))
        self.assertIn("accounts must be a list", " ".join(errors))


if __name__ == "__main__":
    unittest.main()
