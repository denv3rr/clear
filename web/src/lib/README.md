# Lib

Shared frontend utilities, API client, and data helpers.

## Files
- `api.ts`: Typed API client and caching helpers.
- `stream.ts`: Stream/WebSocket helpers.
- `maplibre.ts`, `mapDiagnostics.ts`: Map helpers and diagnostics.
- `systemMetrics.ts`: System metrics formatting helpers.
- `trackerPause.ts`: Local pause toggle for tracker requests.
- `useMeasuredSize.ts`: Hook for measured layout sizing.
- `mockData.ts`: Local mock payloads used during development.

## Usage notes
- Route all API calls through `api.ts` for consistent headers and errors.
