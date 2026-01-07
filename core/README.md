# Core

Foundational application wiring: database configuration, ORM models, and
migrations. This is the lowest-level shared layer used by the CLI and API.

## Files
- `app.py`: Central app bootstrap and shared initialization.
- `database.py`: SQLAlchemy engine/session setup and connection helpers.
- `models.py`: ORM models for persisted entities.
- `migration.py`: Migration helpers and schema evolution utilities.
- `db_management.py`: DB maintenance helpers (init/cleanup/validation).

## Usage notes
- Keep all ORM changes in `models.py` and reflect them in migrations.
- Avoid importing web or CLI modules from `core` to keep the dependency graph
  clean.
