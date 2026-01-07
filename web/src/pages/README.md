# Pages

Route-level views for the web UI. Each file owns data fetching and composition
for a primary feature area.

## Current pages
- `Dashboard.tsx`: Overview metrics, maps, and system summaries.
- `Clients.tsx`: Client/account dashboards and analytics.
- `Intel.tsx`: Intel ingestion and filters.
- `News.tsx`: News feed, sources, and filters.
- `Reports.tsx`: Report exports and summaries.
- `System.tsx`: System diagnostics and maintenance actions.
- `Trackers.tsx`: Live tracker streams and status.

## Usage notes
- Use the shared API client in `web/src/lib/api.ts`.
- Keep page-specific visuals here; move reusable UI into `components/`.
