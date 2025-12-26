import unittest

from modules.client_mgr.data_handler import DataHandler


class TestDataMigrations(unittest.TestCase):
    def test_migrate_legacy_timestamp_with_date(self):
        payload = [
            {
                "accounts": [
                    {
                        "lots": {
                            "AAPL": [
                                {
                                    "qty": 1.0,
                                    "basis": 100.0,
                                    "date": "2025-12-18",
                                    "timestamp": "LEGACY",
                                }
                            ]
                        }
                    }
                ]
            }
        ]
        migrated, changed = DataHandler._migrate_clients_payload(payload)
        self.assertTrue(changed)
        ts = migrated[0]["accounts"][0]["lots"]["AAPL"][0]["timestamp"]
        self.assertEqual(ts, "2025-12-18T00:00:00")

    def test_migrate_space_timestamp(self):
        payload = [
            {
                "accounts": [
                    {
                        "lots": {
                            "AAPL": [
                                {
                                    "qty": 1.0,
                                    "basis": 100.0,
                                    "timestamp": "2025-12-18 01:51:36",
                                }
                            ]
                        }
                    }
                ]
            }
        ]
        migrated, changed = DataHandler._migrate_clients_payload(payload)
        self.assertTrue(changed)
        ts = migrated[0]["accounts"][0]["lots"]["AAPL"][0]["timestamp"]
        self.assertEqual(ts, "2025-12-18T01:51:36")

    def test_migrate_date_only_timestamp(self):
        payload = [
            {
                "accounts": [
                    {
                        "lots": {
                            "AAPL": [
                                {
                                    "qty": 1.0,
                                    "basis": 100.0,
                                    "timestamp": "2024-01-02",
                                }
                            ]
                        }
                    }
                ]
            }
        ]
        migrated, changed = DataHandler._migrate_clients_payload(payload)
        self.assertTrue(changed)
        ts = migrated[0]["accounts"][0]["lots"]["AAPL"][0]["timestamp"]
        self.assertEqual(ts, "2024-01-02T00:00:00")

    def test_no_change_for_iso(self):
        payload = [
            {
                "accounts": [
                    {
                        "lots": {
                            "AAPL": [
                                {
                                    "qty": 1.0,
                                    "basis": 100.0,
                                    "timestamp": "2025-12-18T01:51:36",
                                }
                            ]
                        }
                    }
                ]
            }
        ]
        migrated, changed = DataHandler._migrate_clients_payload(payload)
        self.assertFalse(changed)
        ts = migrated[0]["accounts"][0]["lots"]["AAPL"][0]["timestamp"]
        self.assertEqual(ts, "2025-12-18T01:51:36")


if __name__ == "__main__":
    unittest.main()
