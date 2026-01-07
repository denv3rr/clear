# Diagnostics Guide

This document captures how diagnostics, system info, and feed health should stay consistent across CLI, API, and web UI.

## Sources of Truth
- System metrics: `utils/system.py` (SystemHost), used by CLI and API diagnostics.
- Client/account counts + duplicates: `modules/client_store.py` and DB-backed stores.
- Feed registry: `modules/market_data/registry.py` aggregates configured sources and health.
- Tracker snapshot health: `modules/market_data/trackers.py` snapshot with warnings.

## API Surfaces
- `/api/tools/diagnostics` returns system info, client counts, tracker summary, duplicate counts, orphaned counts, and feed registry summary.
- Diagnostics payloads should include `meta` (route, source, timestamp, warnings) for provenance.

## Feed Registry Health
- Registry sources include market, trackers, intel, osint, and RSS news collectors.
- Health statuses: `ok`, `degraded`, `backoff`, `unknown`.
- Warnings should be emitted when all sources in a category are unconfigured or degraded.

## UI/CLI Expectations
- CLI Settings diagnostics should match API registry summary + health counts.
- System page should display registry counts, issues, and recent health warnings.
- Avoid per-page metric calculations; use shared helpers to reduce drift.

## Data Consistency Checks
- CPU/memory should come from SystemHost only; do not recompute with different sampling windows.
- Client/account totals should match DB counts and view-model payloads.
- Diagnostics numbers should be validated in tests after refactors or data migrations.

## Testing
- `python -m pytest` covers core diagnostics and API payloads.
- Add contract tests when new diagnostics fields are added or renamed.
