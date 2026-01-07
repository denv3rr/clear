# Data Integrity Guide

This document defines the data integrity expectations for clients, accounts, holdings, and diagnostics.

## Sources of Truth
- SQLite DB is the source of truth for client/account data.
- JSON files are export/import only (no direct reads except migrations).
- Diagnostics counts must match DB-backed stores.

## Safety Rules
- Bulk saves must never delete missing clients/accounts unless explicitly allowed.
- All merges should be additive by default; destructive behavior must be guarded and logged.
- Orphaned holdings/lots should be detected and cleaned via maintenance endpoints.

## Duplicate Handling
- Duplicate account detection should ignore volatile fields (e.g., current value) and normalize lots/manual holdings.
- Cleanup endpoints must report remaining duplicate counts after removal.

## Validation
- Validate incoming payload schemas for API and CLI input.
- Reject partial or empty payloads when required fields are missing.
- Surface warnings via `meta` when data is stale or incomplete.

## Testing
- Add tests for DB/JSON parity and duplicate cleanup.
- Add tests for orphan detection and cleanup endpoints.
- Add tests for safe-save guards (no accidental deletes on partial payloads).
