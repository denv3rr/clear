from __future__ import annotations

import unittest
import uuid
from typing import Any, Dict, List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import models
from modules.client_mgr.schema import Client
from modules.client_store import DbClientStore

# Use an in-memory SQLite database for testing
engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TestDbClientStorePydantic(unittest.TestCase):
    def setUp(self):
        models.Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.store = DbClientStore(self.db)

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=engine)

    def test_sync_clients_create_and_overwrite(self):
        # 1. Create a client
        client_id = str(uuid.uuid4())
        payload1 = {
            "client_id": client_id,
            "name": "Test Client 1",
            "accounts": [
                {
                    "account_id": str(uuid.uuid4()),
                    "account_name": "Account 1",
                    "account_type": "Taxable",
                }
            ],
        }
        self.store.sync_clients([payload1])

        # Verify client was created
        clients = self.store.fetch_all_clients()
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["name"], "Test Client 1")
        self.assertEqual(len(clients[0]["accounts"]), 1)
        self.assertEqual(clients[0]["accounts"][0]["account_name"], "Account 1")

        # 2. Update the client
        payload2 = {
            "client_id": client_id,
            "name": "Test Client 1 Updated",
            "accounts": [
                {
                    "account_id": clients[0]["accounts"][0]["account_id"],
                    "account_name": "Account 1 Updated",
                    "account_type": "Taxable",
                }
            ],
        }
        self.store.sync_clients([payload2], overwrite=True)

        # Verify client was updated
        clients = self.store.fetch_all_clients()
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["name"], "Test Client 1 Updated")
        self.assertEqual(len(clients[0]["accounts"]), 1)
        self.assertEqual(clients[0]["accounts"][0]["account_name"], "Account 1 Updated")

    def test_sync_clients_delete_missing(self):
        # 1. Create two clients
        client_id_1 = str(uuid.uuid4())
        client_id_2 = str(uuid.uuid4())
        payloads = [
            {
                "client_id": client_id_1,
                "name": "Client to Keep",
                "accounts": [],
            },
            {
                "client_id": client_id_2,
                "name": "Client to Delete",
                "accounts": [],
            },
        ]
        self.store.sync_clients(payloads)
        self.assertEqual(len(self.store.fetch_all_clients()), 2)

        # 2. Sync with only one client and delete_missing=True
        self.store.sync_clients([payloads[0]], delete_missing=True)

        # Verify the second client was deleted
        clients = self.store.fetch_all_clients()
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["client_id"], client_id_1)

    def test_sync_clients_default_keeps_missing(self):
        client_id_1 = str(uuid.uuid4())
        client_id_2 = str(uuid.uuid4())
        payloads = [
            {"client_id": client_id_1, "name": "Client A", "accounts": []},
            {"client_id": client_id_2, "name": "Client B", "accounts": []},
        ]
        self.store.sync_clients(payloads)
        self.assertEqual(len(self.store.fetch_all_clients()), 2)

        # Default behavior should keep missing clients unless explicitly deleted.
        self.store.sync_clients([payloads[0]])
        clients = self.store.fetch_all_clients()
        self.assertEqual(len(clients), 2)

    def test_sync_clients_generates_missing_ids(self):
        payloads = [
            {
                "name": "Client Without ID",
                "accounts": [
                    {
                        "account_name": "Account Without ID",
                        "account_type": "Taxable",
                    }
                ],
            }
        ]
        self.store.sync_clients(payloads)
        clients = self.store.fetch_all_clients()
        self.assertEqual(len(clients), 1)
        self.assertTrue(clients[0]["client_id"])
        self.assertEqual(len(clients[0]["accounts"]), 1)
        self.assertTrue(clients[0]["accounts"][0]["account_id"])


if __name__ == "__main__":
    unittest.main()
