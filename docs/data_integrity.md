# Data Integrity Guide

This document defines the data integrity expectations for clients, accounts, holdings, and diagnostics.

## Sources of Truth
- SQLite DB is the source of truth for client/account data.
- Canonical lots live on `accounts.lots` JSON. Canonical holding quantities live on `accounts.holdings_map` JSON.
- Relational `holdings` and `lots` tables are unused leftovers. `DbClientStore` does not write those tables.
- JSON files are export/import only (no direct reads except migrations).
- Diagnostics counts must match DB-backed stores.

## Safety Rules
- Bulk saves must never delete missing clients/accounts unless explicitly allowed.
- All merges should be additive by default; destructive behavior must be guarded and logged.
- Relational leftover holdings/lots (orphan rows in the unused tables) should be detected and cleaned via maintenance endpoints. That cleanup does not rewrite canonical JSON lots.
- Diagnostics also report canonical JSON integrity: holdings tickers missing lot history, and holdings quantity versus the sum of lot quantities.

## Duplicate Handling
- Duplicate account detection uses the same identity key as write guards (`name` + `account_type` + `ownership_type` + `custodian`).
- Volatile fields such as current value, interval, extra, holdings, and lots do not create a distinct account identity.
- Cleanup endpoints must report remaining duplicate counts after removal.

## Validation
- Validate incoming payload schemas for API and CLI input.
- Reject partial or empty payloads when required fields are missing.
- Surface warnings via `meta` when data is stale or incomplete.

## Testing
- Add tests for DB/JSON parity and duplicate cleanup.
- Add tests for orphan detection and cleanup endpoints.
- Add tests for safe-save guards (no accidental deletes on partial payloads).
