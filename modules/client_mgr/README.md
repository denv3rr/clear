# Client Manager

Client portfolio analytics and reporting pipeline. This folder owns the core
logic used by the CLI and API to compute risk, regime, and pattern outputs.

## Key modules
- `manager.py`: Orchestrates analytics workflows and payload assembly.
- `calculations.py`: Canonical math utilities (annualization, CAPM, core stats).
- `toolkit.py`: Aggregates tool outputs; delegates to view modules.
- `patterns.py`: Pattern suite payloads, surfaces, and renderers.
- `risk_views.py`: Risk summaries and view-ready payloads.
- `regime.py`: Regime model calculations and metrics.
- `regime_views.py`: Regime view payloads and renderers.
- `holdings.py`, `valuation.py`, `tax.py`: Holdings, valuation, and tax logic.
- `schema.py`, `payloads.py`, `data.py`, `data_handler.py`: Payload schemas and
  ingestion helpers.

## Usage notes
- Keep math in `calculations.py`; renderers should consume computed results.
- View-model outputs must be JSON-ready for the web API.
