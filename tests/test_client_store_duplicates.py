from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.database as database
import core.db_management as db_management
from core import models
import modules.client_store as client_store


def _setup_temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "clients.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(db_management, "engine", engine)
    monkeypatch.setattr(client_store, "SessionLocal", session_local)
    return session_local


def _seed_duplicates(session):
    client = models.Client(client_uid="c1", name="Dup Client")
    session.add(client)
    session.flush()
    account_payload = dict(
        name="Primary",
        account_type="Taxable",
        ownership_type="Individual",
        custodian="Fidelity",
        tags=["Core"],
        tax_settings={"jurisdiction": "US"},
        holdings_map={"AAPL": 1.0},
        lots={"AAPL": [{"qty": 1.0, "basis": 100.0, "timestamp": "2024-01-01T00:00:00"}]},
        manual_holdings=[],
        client_id=client.id,
    )
    session.add(
        models.Account(
            account_uid="a1",
            extra={"source": "seed"},
            current_value=100.0,
            active_interval="1M",
            **account_payload,
        )
    )
    session.add(
        models.Account(
            account_uid="a2",
            extra={"note": "dup"},
            current_value=250.0,
            active_interval="1Y",
            **account_payload,
        )
    )
    session.commit()


def test_detect_duplicate_accounts(tmp_path, monkeypatch):
    session_local = _setup_temp_db(tmp_path, monkeypatch)
    db_management.create_db_and_tables()
    session = session_local()
    try:
        _seed_duplicates(session)
        store = client_store.DbClientStore(session)
        result = store.find_duplicate_accounts()
        assert result["count"] == 1
        assert result["clients"] == 1
        assert result["details"][0]["duplicate_count"] == 1
    finally:
        session.close()


def test_cleanup_duplicate_accounts(tmp_path, monkeypatch):
    session_local = _setup_temp_db(tmp_path, monkeypatch)
    db_management.create_db_and_tables()
    session = session_local()
    try:
        _seed_duplicates(session)
        store = client_store.DbClientStore(session)
        result = store.remove_duplicate_accounts()
        assert result["removed"] == 1
        assert result["remaining"]["count"] == 0
        assert session.query(models.Account).count() == 1
    finally:
        session.close()


def test_detect_duplicates_with_legacy_holdings(tmp_path, monkeypatch):
    session_local = _setup_temp_db(tmp_path, monkeypatch)
    db_management.create_db_and_tables()
    session = session_local()
    try:
        client = models.Client(client_uid="c2", name="Legacy Client")
        session.add(client)
        session.flush()
        account_a = models.Account(account_uid="legacy-a", name="Legacy", account_type="Taxable", client_id=client.id)
        account_b = models.Account(account_uid="legacy-b", name="Legacy", account_type="Taxable", client_id=client.id)
        session.add(account_a)
        session.add(account_b)
        session.flush()
        session.add(models.Holding(ticker="AAPL", quantity=1.0, account_id=account_a.id))
        session.add(models.Holding(ticker="AAPL", quantity=1.0, account_id=account_b.id))
        session.commit()
        store = client_store.DbClientStore(session)
        result = store.find_duplicate_accounts()
        assert result["count"] == 1
    finally:
        session.close()


def test_detect_duplicates_with_lot_variants(tmp_path, monkeypatch):
    session_local = _setup_temp_db(tmp_path, monkeypatch)
    db_management.create_db_and_tables()
    session = session_local()
    try:
        client = models.Client(client_uid="c3", name="Lot Client")
        session.add(client)
        session.flush()
        account_payload = dict(
            name=" Primary ",
            account_type="Taxable",
            ownership_type="Individual",
            custodian="Fidelity",
            tags=["Core", "LongTerm"],
            tax_settings={"jurisdiction": "US", "account_currency": "USD"},
            holdings_map={"AAPL": 1.0},
            manual_holdings=[{"name": "Real Estate", "total_value": 1000.0}],
            client_id=client.id,
        )
        session.add(
            models.Account(
                account_uid="lot-a",
                lots={
                    "AAPL": [
                        {"qty": 1.0, "basis": 100.0, "timestamp": "2024-01-01T00:00:00"}
                    ]
                },
                **account_payload,
            )
        )
        session.add(
            models.Account(
                account_uid="lot-b",
                lots={
                    "AAPL": [
                        {
                            "basis": 100.0,
                            "qty": 1.0,
                            "timestamp": "2024-01-01T00:00:00",
                            "source": "LEGACY_DB",
                            "kind": "lot",
                        }
                    ]
                },
                **account_payload,
            )
        )
        session.commit()
        store = client_store.DbClientStore(session)
        result = store.find_duplicate_accounts()
        assert result["count"] == 1
    finally:
        session.close()
