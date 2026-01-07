from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from core.database import SessionLocal
from core.db_management import create_db_and_tables
from modules.client_mgr.schema import Client
from modules.client_store import DbClientStore


def migrate_data() -> None:
    """
    Migrates data from the JSON files to the database.
    """
    db = SessionLocal()
    try:
        with open("data/clients.json", "r", encoding="utf-8") as f:
            clients_raw_data = json.load(f)

        if not isinstance(clients_raw_data, list):
            logging.error("data/clients.json should contain a list of clients.")
            return

        clients_data = [Client.model_validate(c) for c in clients_raw_data]
        logging.info(f"Found {len(clients_data)} clients in data/clients.json to migrate.")

        store = DbClientStore(db)
        store.sync_clients(
            [client.model_dump() for client in clients_data],
            delete_missing=False,
            overwrite=False,
        )
        logging.info("Data migration completed successfully.")

    except (json.JSONDecodeError, ValidationError) as e:
        logging.error(f"Error migrating data from data/clients.json: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_db_and_tables()
    migrate_data()
