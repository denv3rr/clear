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
        extra={"source": "seed"},
        current_value=100.0,
        active_interval="1M",
        client_id=client.id,
    )
    session.add(models.Account(account_uid="a1", **account_payload))
    session.add(models.Account(account_uid="a2", **account_payload))
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
        assert session.query(models.Account).count() == 1
    finally:
        session.close()
