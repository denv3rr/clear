from __future__ import annotations

import json

from core.database import SessionLocal
from core.db_management import create_db_and_tables
from modules.client_mgr.payloads import normalize_clients_payload
from modules.client_store import DbClientStore


def migrate_data() -> None:
    """
    Migrates data from the JSON files to the database.
    """
    db = SessionLocal()
    try:
        with open("data/clients.json", "r", encoding="utf-8") as f:
            clients_data = json.load(f)
        clients_data, _ = normalize_clients_payload(clients_data)
        store = DbClientStore(db)
        store.sync_clients(
            clients_data if isinstance(clients_data, list) else [],
            delete_missing=False,
            overwrite=False,
        )
    finally:
        db.close()


if __name__ == "__main__":
    create_db_and_tables()
    migrate_data()
