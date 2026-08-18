import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import core.database as database
import core.db_management as db_management
from core import models
import modules.client_store as client_store
from web_api import diagnostics


def _setup_temp_db(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(db_management, "engine", engine)
    monkeypatch.setattr(client_store, "SessionLocal", session_local)
    monkeypatch.setattr(diagnostics, "SessionLocal", session_local)
    return session_local


def test_session_scope_commits_owned_session(monkeypatch):
    session_local = _setup_temp_db(monkeypatch)
    db_management.create_db_and_tables()
    with client_store._session_scope(None) as db:
        db.add(models.Client(client_uid="owned-commit", name="Owned Commit"))
    session = session_local()
    try:
        assert session.query(models.Client).filter_by(client_uid="owned-commit").first() is not None
    finally:
        session.close()


def test_session_scope_rollbacks_owned_session(monkeypatch):
    session_local = _setup_temp_db(monkeypatch)
    db_management.create_db_and_tables()
    with pytest.raises(RuntimeError, match="forced failure"):
        with client_store._session_scope(None) as db:
            db.add(models.Client(client_uid="owned-fail", name="Owned Fail"))
            db.flush()
            raise RuntimeError("forced failure")
    session = session_local()
    try:
        assert session.query(models.Client).filter_by(client_uid="owned-fail").first() is None
    finally:
        session.close()


def test_session_scope_does_not_commit_caller_session(monkeypatch):
    session_local = _setup_temp_db(monkeypatch)
    db_management.create_db_and_tables()
    session = session_local()
    try:
        with client_store._session_scope(session) as db:
            db.add(models.Client(client_uid="caller-owned", name="Caller Owned"))
            db.flush()
        session.rollback()
        assert session.query(models.Client).filter_by(client_uid="caller-owned").first() is None
    finally:
        session.close()


def test_update_account_recomputes_holdings_from_lots(monkeypatch):
    session_local = _setup_temp_db(monkeypatch)
    db_management.create_db_and_tables()
    session = session_local()
    try:
        store = client_store.DbClientStore(session)
        store.create_client(
            {
                "client_id": "lot-client",
                "name": "Lot Client",
                "accounts": [],
            }
        )
        store.create_account(
            "lot-client",
            {
                "account_id": "acct-1",
                "account_name": "Brokerage",
                "account_type": "Taxable",
                "holdings": {"AAPL": 1.0},
                "lots": {
                    "AAPL": [{"qty": 1.0, "basis": 100.0, "timestamp": "2024-01-01T00:00:00"}]
                },
            },
        )
        updated = store.update_account(
            "lot-client",
            "acct-1",
            {
                "lots": {
                    "msft": [
                        {"qty": 2.0, "basis": 20.0, "timestamp": "2024-02-01T00:00:00"},
                        {"qty": 2.5, "basis": 22.0, "timestamp": "2024-03-01T00:00:00"},
                    ]
                }
            },
        )
        assert updated is not None
        assert updated["lots"]["MSFT"]
        assert "AAPL" not in updated["lots"]
        assert updated["holdings"] == {"MSFT": 4.5}
        assert "AAPL" not in updated["holdings"]
    finally:
        session.close()


def test_update_account_holdings_without_lots_leaves_lots(monkeypatch):
    session_local = _setup_temp_db(monkeypatch)
    db_management.create_db_and_tables()
    session = session_local()
    try:
        store = client_store.DbClientStore(session)
        store.create_client(
            {
                "client_id": "holdings-only",
                "name": "Holdings Only Client",
                "accounts": [],
            }
        )
        store.create_account(
            "holdings-only",
            {
                "account_id": "acct-1",
                "account_name": "Brokerage",
                "account_type": "Taxable",
                "holdings": {"AAPL": 1.0},
                "lots": {
                    "AAPL": [{"qty": 1.0, "basis": 100.0, "timestamp": "2024-01-01T00:00:00"}]
                },
            },
        )
        updated = store.update_account(
            "holdings-only",
            "acct-1",
            {"holdings": {"AAPL": 9.0}},
        )
        assert updated is not None
        assert updated["holdings"]["AAPL"] == 9.0
        assert updated["lots"]["AAPL"][0]["qty"] == 1.0
    finally:
        session.close()


def test_orphaned_counts_keeps_relational_and_adds_canonical(monkeypatch):
    session_local = _setup_temp_db(monkeypatch)
    db_management.create_db_and_tables()
    session = session_local()
    try:
        client = models.Client(client_uid="canon-1", name="Canonical Client")
        session.add(client)
        session.flush()
        session.add(
            models.Account(
                account_uid="acct-canon",
                name="Primary",
                account_type="Taxable",
                holdings_map={"AAPL": 5.0, "MSFT": 2.0},
                lots={
                    "AAPL": [
                        {"qty": 3.0, "basis": 10.0, "timestamp": "2024-01-01T00:00:00"}
                    ]
                },
                client_id=client.id,
            )
        )
        session.execute(text("PRAGMA foreign_keys=OFF"))
        session.add(models.Holding(ticker="X", quantity=1.0, account_id=999))
        session.add(
            models.Lot(
                purchase_date=None,
                purchase_price=1.0,
                quantity=1.0,
                holding_id=999,
            )
        )
        session.commit()
    finally:
        session.close()

    counts = diagnostics.orphaned_counts()
    assert counts["holdings"] == 1
    assert counts["lots"] == 1
    assert counts["canonical_holdings_missing_lots"] == 1
    assert counts["canonical_lots_qty_mismatch"] == 1
