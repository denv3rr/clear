from __future__ import annotations
import json
from datetime import datetime
from core.database import SessionLocal
from core import models
from core.db_management import create_db_and_tables

def migrate_data():
    """
    Migrates data from the JSON files to the database.
    """
    db = SessionLocal()
    try:
        with open("data/clients.json", "r") as f:
            clients_data = json.load(f)

        clients_to_add = []
        accounts_to_add = []
        holdings_to_add = []
        lots_to_add = []

        for client_data in clients_data:
            client = models.Client(
                name=client_data["name"],
                risk_profile=client_data.get("risk_profile"),
            )
            clients_to_add.append(client)

            for account_data in client_data.get("accounts", []):
                account = models.Account(
                    name=account_data["account_name"],
                    account_type=account_data.get("account_type"),
                    client=client,
                )
                accounts_to_add.append(account)

                for ticker, quantity in account_data.get("holdings", {}).items():
                    holding = models.Holding(
                        ticker=ticker,
                        quantity=quantity,
                        account=account,
                    )
                    holdings_to_add.append(holding)

                    for lot_data in account_data.get("lots", {}).get(ticker, []):
                        lot = models.Lot(
                            purchase_date=datetime.fromisoformat(lot_data.get("timestamp")) if lot_data.get("timestamp") else None,
                            purchase_price=lot_data.get("basis"),
                            quantity=lot_data.get("qty"),
                            holding=holding,
                        )
                        lots_to_add.append(lot)
        
        db.add_all(clients_to_add)
        db.add_all(accounts_to_add)
        db.add_all(holdings_to_add)
        db.add_all(lots_to_add)
        db.commit()

    finally:
        db.close()

if __name__ == "__main__":
    create_db_and_tables()
    migrate_data()
