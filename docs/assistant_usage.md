# Assistant Usage

This document describes how to use the assistant across API, web UI, and CLI.

## API
- Endpoint: `POST /api/assistant/query`
- Export history: `POST /api/assistant/history/export`
- Payload:
  - `question` (string)
  - `context` (optional: client_id, account_id, region, industry)
  - `sources` (optional list for news filtering)
  - `mode` (summary | explain | compare | timeline)
- Response:
  - `answer` (string)
  - `sources` (list)
  - `confidence` (Low/Medium/High)
  - `warnings` (list)
  - `routing` (rule + handler, when available)
  - `meta` (route, source, timestamp, warnings)
- Export response:
  - `export` (methodology, lineage, entries)
  - `markdown` (when format is `md` or `markdown`)

## Web
- The chat drawer is available in the global layout and surfaces response metadata.
- Context selectors include region, industry, tickers, sources, client, and account.
- Client/account IDs are validated and account-only scopes are resolved when possible.
- Context is persisted locally for the active browser session profile.

## CLI
- Assistant module in the main menu mirrors API payloads.
- Context can be edited and recent responses are stored in history.
- Export history from the assistant menu to `data/exports/` in JSON or Markdown.

## Constraints
- Deterministic outputs only; no simulated math.
- Unsupported modes return 501 with explicit warnings.
