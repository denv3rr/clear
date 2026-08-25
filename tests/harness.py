"""Isolated ephemeral SQLite/API harness for positive-path tests.

Phase 1 of docs/standards_remediation_plan.md. This harness never points
at operator runtime databases. Positive-path API tests should use it or
captured fixtures with provenance, not fabricated success stubs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DIR = ROOT / "test_runtime" / "isolated"


def isolated_sqlite_path(
    request,
    filename: str,
    runtime_dir: Path | None = None,
) -> Path:
    base = runtime_dir or DEFAULT_RUNTIME_DIR
    base.mkdir(parents=True, exist_ok=True)
    case_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.nodeid)
    case_dir = base / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    db_path = case_dir / filename
    cleanup_sqlite_files(db_path, remove_dir=False)
    case_dir.mkdir(parents=True, exist_ok=True)
    return db_path


def cleanup_sqlite_files(db_path: Path, *, remove_dir: bool = True) -> None:
    for suffix in ("", "-journal", "-shm", "-wal"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()
    if not remove_dir:
        return
    try:
        db_path.parent.rmdir()
    except OSError:
        pass


def make_isolated_engine(db_path: Path):
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, session_local


def isolated_sqlite_session(
    request,
    filename: str,
    runtime_dir: Path | None = None,
) -> Iterator[tuple[object, object, Path]]:
    """Yield session, engine, and path; always dispose and delete files."""
    from core.database import Base

    db_path = isolated_sqlite_path(request, filename, runtime_dir=runtime_dir)
    engine, session_local = make_isolated_engine(db_path)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = session_local()
    try:
        yield session, engine, db_path
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        cleanup_sqlite_files(db_path)
