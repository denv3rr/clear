# Components

Reusable UI and layout building blocks for the web app.

## Structure
- `layout/`: App shell, navigation, and shared page scaffolding.
- `osint/`: Shared OSINT workspace composition used by Overview and the `/osint` deep-link route.
- `ui/`: Reusable widgets, charts, cards, banners, and controls.

## Usage notes
- Favor design tokens in `web/src/design/tokens.ts` for colors/spacing.
- Avoid one-off styling in pages; add shared components here instead.
