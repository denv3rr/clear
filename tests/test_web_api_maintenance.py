import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import core.database as database
import core.db_management as db_management
from core import models
from web_api import diagnostics
from web_api.app import app
from web_api.routes import maintenance as maintenance_routes


TEST_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "test_runtime" / "web_api_maintenance"


def _isolated_db_path(request, filename: str) -> Path:
    TEST_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    case_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.nodeid)
    case_dir = TEST_RUNTIME_DIR / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    db_path = case_dir / filename
    for suffix in ("", "-journal", "-shm", "-wal"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()
    return db_path


def _cleanup_sqlite_files(db_path: Path) -> None:
    for suffix in ("", "-journal", "-shm", "-wal"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()
    try:
        db_path.parent.rmdir()
    except OSError:
        pass


def _setup_temp_db(request, monkeypatch):
    db_path = _isolated_db_path(request, "maintenance.db")
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(db_management, "engine", engine)
    monkeypatch.setattr(maintenance_routes, "SessionLocal", session_local)
    monkeypatch.setattr(diagnostics, "SessionLocal", session_local)
    return session_local, engine, db_path


@pytest.fixture()
def client(request, monkeypatch):
    session_local, engine, db_path = _setup_temp_db(request, monkeypatch)
    db_management.create_db_and_tables()
    monkeypatch.setenv("CLEAR_WEB_API_KEY", "test_key")
    try:
        yield TestClient(app, headers={"X-API-Key": "test_key"}), session_local
    finally:
        engine.dispose()
        _cleanup_sqlite_files(db_path)


def test_cleanup_orphans(client):
    test_client, session_local = client
    session = session_local()
    try:
        session.execute(text("PRAGMA foreign_keys=OFF"))
        session.add(models.Holding(ticker="AAPL", quantity=1.0, account_id=999))
        session.add(
            models.Lot(
                purchase_date=None,
                purchase_price=10.0,
                quantity=1.0,
                holding_id=999,
            )
        )
        session.commit()
    finally:
        session.close()

    resp = test_client.post("/api/maintenance/cleanup-orphans", json={"confirm": True})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["removed_holdings"] == 1
    assert payload["removed_lots"] == 1


def test_cleanup_orphans_requires_confirm(client):
    test_client, _ = client
    resp = test_client.post("/api/maintenance/cleanup-orphans", json={"confirm": False})
    assert resp.status_code == 400


def test_clear_report_cache_requires_confirm(client):
    test_client, _ = client
    resp = test_client.post("/api/maintenance/clear-report-cache", json={"confirm": False})
    assert resp.status_code == 400


def test_normalize_lots_requires_confirm(client):
    test_client, _ = client
    resp = test_client.post("/api/maintenance/normalize-lots", json={"confirm": False})
    assert resp.status_code == 400
