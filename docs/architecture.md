# Architecture Standards

These standards keep CLI, API, and web UI modular and future-proof.

## Core Principles
- Single source of truth for business logic and view-models.
- Web UI and CLI render the same view-model payloads.
- API is modularized by domain (routers) and shares auth dependencies.
- Design system is tokenized and components are reusable across pages.

## API Layout
- `web_api/routes/*` contains domain routers (trackers, intel, clients, reports, settings, tools).
- `web_api/auth.py` provides shared API key auth dependency.
- `web_api/app.py` only composes routers + middleware.

## UI Layout
- `web/src/design/tokens.ts` defines theme tokens and base colors.
- `web/src/components/ui/*` includes reusable primitives (Card, SectionHeader, etc).
- `web/src/components/layout/*` hosts global layout components (Sidebar, AppShell).
- `web/src/config/*` hosts navigation and shared UI config.
- `web/src/lib/api.ts` hosts the shared API client, caching, and hooks.
- `web/src/lib/stream.ts` hosts WebSocket hooks for live data.
- `web/src/pages/*` contains feature pages; pages must use shared components and `useApi`.

## Extension Checklist
- Add a view-model and/or shared helper in `modules/*`.
- Add an API endpoint in `web_api/routes/<domain>.py`.
- Add or reuse UI components in `web/src/components`.
- Add tests for new view-models + API routes.
- Update `AGENTS.md` if system design changes.
