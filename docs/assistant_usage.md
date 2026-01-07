# Assistant Usage

This document describes how to use the assistant across API, web UI, and CLI.

## API
- Endpoint: `POST /api/assistant/query`
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
  - `meta` (route, source, timestamp, warnings)

## Web
- The chat drawer is available in the global layout and surfaces response metadata.
- Context selectors include region, industry, tickers, sources, client, and account.

## CLI
- Assistant module in the main menu mirrors API payloads.
- Context can be edited and recent responses are stored in history.

## Constraints
- Deterministic outputs only; no simulated math.
- Unsupported modes return 501 with explicit warnings.
