# AI Assistant Plan (Draft)

## Goals
- Provide a deterministic insight layer on top of existing analytics, news, and client data.
- Keep all calculations source-driven (no simulations, no example math).
- Support optional local model integrations without changing core outputs.

## Scope
- Summarize existing analytics (risk/regime/patterns/diagnostics) and news coverage.
- Answer questions using user data with clear citations to data sources.
- Offer explanations of metrics and anomalies without inventing values.

## Data Contracts
- Read-only access to:
  - `/api/clients`, `/api/clients/{id}`, `/api/clients/{id}/accounts/{id}`
  - `/api/intel/summary`, `/api/intel/weather`, `/api/intel/conflict`, `/api/news`
  - `/api/trackers`, `/api/diagnostics`, `/api/settings/system`
- Only use JSON-ready view-models already exposed by the API.
- Do not compute new values unless backed by documented formulas in code.

## Interaction Model
- UI: floating chat drawer anchored in the top nav, expandable from any page.
- CLI: shared "Ask Clear" command with context flags (client, account, region).
- API: `/api/assistant/query` endpoint (auth gated) that accepts:
  - `question` (string)
  - `context` (optional selectors: client_id, account_id, region, industry)
  - `sources` (optional list for news filtering)
  - `mode` (summary | explain | compare | timeline)

## Behavior Rules
- Always return structured output with:
  - `answer` (string)
  - `sources` (list of data refs + timestamps)
  - `confidence` (Low/Medium/High based on data availability)
  - `warnings` (missing data, stale cache, or blocked sources)
- No hallucinated numbers or placeholder examples.
- If inputs are missing, return "Unavailable" with a reason.

## Model Options
- Default: rules-based summarizer and templated narratives over deterministic data.
- Optional: local model integration (e.g., via Ollama) for language polish only.
- Never allow the model to change numeric values, only rephrase.

## Implementation Plan
1) Add shared prompt context builder for analytics + news payloads.
2) Implement API endpoint with strict schema validation and rate limits.
3) Add UI chat drawer with history + export.
4) Add CLI command that mirrors API payloads.
5) Add tests for schema validation and deterministic output constraints.

For the agent-based architecture, please consult the `agents/` folder.
