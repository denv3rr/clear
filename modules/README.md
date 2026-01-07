# Modules

Shared domain logic used by both the CLI and web API. This is where data
processing, analytics, and view-model shaping live.

## Top-level files
- `client_store.py`: Client/account persistence and sync logic.
- `view_models.py`: JSON-ready view models for API and CLI renderers.

## `client_mgr/`
Client portfolio analytics, reporting, and toolkit logic.

- `manager.py`: Orchestration entry point for client/account analytics.
- `calculations.py`: Centralized math utilities (risk, return, annualization).
- `toolkit.py`: Aggregates tools and delegates to the specialized view modules.
- `patterns.py`, `risk_views.py`, `regime_views.py`: Render-ready payloads and
  surfaces for pattern/risk/regime analysis.
- `regime.py`: Regime model computations and summaries.
- `holdings.py`, `valuation.py`, `tax.py`: Holdings modeling, valuation, tax
  computations.
- `payloads.py`, `schema.py`, `data.py`, `data_handler.py`: Schema/payload
  helpers and data ingestion.

## Usage notes
- Keep calculations centralized in `calculations.py`.
- Expose JSON-ready payloads for the API and reuse them in CLI renderers.
