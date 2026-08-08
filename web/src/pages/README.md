# Pages

Route-level views for the web UI. Each file owns data fetching and composition
for a primary feature area.

## Current pages
- `Dashboard.tsx`: Overview metrics, client/account snapshot, and the embedded OSINT workspace entry.
- `Clients.tsx`: Client/account dashboards and analytics.
- `Osint.tsx`: Deep-link route for the shared OSINT workspace; the primary entry now also lives on Overview.
- `Intel.tsx`: Intel ingestion and filters (OSINT tab).
- `News.tsx`: News feed, sources, and filters (OSINT tab).
- `Reports.tsx`: Report exports and summaries.
- `System.tsx`: System diagnostics and maintenance actions.
- `Trackers.tsx`: Live tracker streams and status (OSINT tab).

## Usage notes
- Use the shared API client in `web/src/lib/api.ts`.
- Keep page-specific visuals here; move reusable UI into `components/`.
