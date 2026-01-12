# Pages

Route-level views for the web UI. Each file owns data fetching and composition
for a primary feature area.

## Current pages
- `Dashboard.tsx`: Overview metrics, maps, and system summaries.
- `Clients.tsx`: Client/account dashboards and analytics.
- `Osint.tsx`: OSINT hub for trackers, intel, and news.
- `Intel.tsx`: Intel ingestion and filters (OSINT tab).
- `News.tsx`: News feed, sources, and filters (OSINT tab).
- `Reports.tsx`: Report exports and summaries.
- `System.tsx`: System diagnostics and maintenance actions.
- `Trackers.tsx`: Live tracker streams and status (OSINT tab).

## Usage notes
- Use the shared API client in `web/src/lib/api.ts`.
- Keep page-specific visuals here; move reusable UI into `components/`.
