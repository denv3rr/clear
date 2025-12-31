from __future__ import annotations

from core.database import Base, engine

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)
