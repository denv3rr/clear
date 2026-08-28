# Design

Design tokens and visual system primitives for the web UI.

## Files
- `tokens.ts`: Color, spacing, typography, and motion tokens.

## Usage notes
- Add new tokens here instead of hardcoding values in components.
- Keep one visually dominant primary workspace per screen.
- New controls should not automatically become permanently visible. Place them
  in the primary workflow, contextual UI, or advanced settings according to
  when the user needs them.
- Preserve product capability through progressive disclosure instead of
  removing advanced functions.
- Technical visualizations must pair precise notation with human-readable
  labels, units, plain-language tooltips, and enough explanation for a
  non-specialist to understand what the visualization represents.
- Do not hide warnings, provenance, freshness, uncertainty, or other critical
  status information to make a screen look calmer.
- Canvas interactions must retain keyboard-operable, non-canvas equivalents.
- See `docs/ui_simplification_plan.md` for the active interaction hierarchy.
