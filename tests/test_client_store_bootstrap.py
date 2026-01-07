import json

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


def _write_clients_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="ascii")


def test_bootstrap_skips_when_db_not_empty(tmp_path, monkeypatch):
    session_local = _setup_temp_db(tmp_path, monkeypatch)
    db_management.create_db_and_tables()
    session = session_local()
    try:
        session.add(models.Client(client_uid="c1", name="Existing Client"))
        session.commit()
    finally:
        session.close()

    clients_path = tmp_path / "clients.json"
    _write_clients_json(
        clients_path,
        [{"client_id": "c2", "name": "Json Client", "accounts": []}],
    )
    monkeypatch.setattr(client_store, "CLIENTS_JSON_PATH", str(clients_path))

    assert client_store.bootstrap_clients_from_json() is False

    session = session_local()
    try:
        assert session.query(models.Client).count() == 1
    finally:
        session.close()


def test_bootstrap_loads_when_db_empty(tmp_path, monkeypatch):
    session_local = _setup_temp_db(tmp_path, monkeypatch)
    db_management.create_db_and_tables()

    clients_path = tmp_path / "clients.json"
    _write_clients_json(
        clients_path,
        [
            {
                "client_id": "c1",
                "name": "Json Client",
                "accounts": [
                    {
                        "account_id": "a1",
                        "account_name": "Main",
                        "holdings": {"AAPL": 2},
                    }
                ],
            }
        ],
    )
    monkeypatch.setattr(client_store, "CLIENTS_JSON_PATH", str(clients_path))

    assert client_store.bootstrap_clients_from_json() is True

    session = session_local()
    try:
        assert session.query(models.Client).count() == 1
        assert session.query(models.Account).count() == 1
    finally:
        session.close()
