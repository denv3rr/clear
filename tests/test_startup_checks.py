import unittest
import io
import os
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import run as startup
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

    def test_dependency_check_uses_import_module_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "requirements.txt").write_text(
                "SQLAlchemy==2.0.45\n",
                encoding="ascii",
            )
            cwd = os.getcwd()
            seen = []

            def fake_find_spec(name):
                seen.append(name)
                return object()

            try:
                os.chdir(tmp)
                with mock.patch.object(
                    startup.importlib.util,
                    "find_spec",
                    side_effect=fake_find_spec,
                ), mock.patch.object(startup.subprocess, "check_call") as check_call:
                    startup.check_and_install_packages()
            finally:
                os.chdir(cwd)

            self.assertEqual(seen, ["sqlalchemy"])
            check_call.assert_not_called()

    def test_empty_clients_json_is_not_reported_as_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp, "data")
            data_dir.mkdir()
            Path(data_dir, "clients.json").write_text("", encoding="ascii")
            cwd = os.getcwd()
            out = io.StringIO()
            try:
                os.chdir(tmp)
                with redirect_stdout(out):
                    startup._validate_clients_json()
            finally:
                os.chdir(cwd)

            self.assertNotIn("Invalid data/clients.json", out.getvalue())


if __name__ == "__main__":
    unittest.main()
