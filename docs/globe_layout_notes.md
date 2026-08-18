# Globe Layout Notes (Phase 5 HUD)

Status: applied on 2026-08-17. This is a layout/HUD pass only. It does not
add globe layers, tracker fixtures, or ReliefWeb/EONET/FIRMS/NWS/USGS sources.

## Research Applied

### Stripe globe writeup
Source: [To design and develop an interactive globe](https://stripe.com/blog/globe)

Applied patterns:

- The globe is the canvas. A sphere uses far less screen area than a 2D world
  map, so overlay chrome should not recapture that space as a card wall.
- Details are concealed for discovery. Deep inspection belongs in a selected
  feature drawer, not as a permanent stack of panels over the planet.
- Country/admin lines are context, not the product. Stripe used borders only
  when they served a specific data story; this repo already treats Natural
  Earth admin-0 lines as de facto context, not legal truth, and that copy stays
  visible in Scene Status.

Not applied:

- No new decorative motion, particle density, or sunflower-dot landmass work.
- No invented geometry or country fills.

### Three.js HUD / FUI patterns
Sources:

- Three.js HUD discussions: DOM overlay vs in-scene HUD
  ([mrdoob/three.js#225](https://github.com/mrdoob/three.js/issues/225),
  [Evermade HUD note](https://www.evermade.fi/insights/pure-three-js-hud/))
- FUI convention: corner clusters, pointer-events none on the canvas host,
  pointer-events auto on compact HUD plates.

Applied patterns:

- Keep the existing DOM overlay HUD rather than baking UI into the WebGL scene.
- Group controls into a left command corner (scene + layers + collapsed
  filters + status) and a right details drawer.
- Do not dump every filter chip at once. Layers stay visible; extra filters
  sit behind a Show Filters control.

Not applied:

- No in-WebGL HUD texture, extra FUI ornament, or new animation library.

### WCAG 2.2 Use of Color (1.4.1)
Source: [WCAG 2.2 SC 1.4.1](https://www.w3.org/TR/WCAG22/#use-of-color)

Applied patterns:

- Layer, lens, camera, and filter chips keep text labels, not color-only
  on/off states.
- Density bars keep a text label and numeric value; the color bar is
  `aria-hidden` and is not the only signal.
- Leaflet fallback tooltips include kind/category/operator text so marker
  color is not the only identity cue.
- Legend swatches stay paired with labels.

Reduced motion is unchanged. Existing `prefers-reduced-motion` handling in
the globe scene and overlay CSS remains the motion contract.

## What Changed

### `GlobeOverlay.tsx`
- Left HUD is now a compact corner: World scene switcher, a single Layers
  cluster (visibility + scope/lens + camera), a collapsed Filters drawer, and
  Scene Status.
- Scene Status still shows freshness/`Unavailable`, reduced-motion/fallback
  notes, warnings, and the de facto admin-context geography line.
- Extra intel/tracker filter chips no longer render until Show Filters is
  opened. An active-filter count remains visible when the drawer is closed.
- Right details drawer still owns Operational Focus, Visible Aggregate, and
  Refresh Scene. The selected-feature inspector now starts with a scannable
  Provenance stack: Source, Layer, Display Scope, Coverage, Feature Warnings,
  Display Note.
- Client context moved from the left wall into the details drawer so the
  globe stays readable.
- No new data layers or fabricated geometry.

### `GlobeDataDensity.tsx`
- Rows are a labeled list with `aria-label` values.
- Color remains a secondary width cue, not the only count signal.

### `Trackers.tsx`
- Leaflet fallback markers now `bindTooltip` with text identity and click to
  `setSelectedId` + `setFeedOpen`, matching the MapLibre click path.
- Leaflet still caps rendered points (raised slightly to 240 because markers
  are now labeled).
- Stream disablement is always visible: a `role="status"` banner plus a map
  chip when tracking is paused or server filters (category/country/operator)
  force snapshot polling.

### Tests and docs
- `web/tests/trackers.spec.ts` covers the pause and server-filter stream
  status copy.
- No tracker globe fixtures were added.
- This file and a short note in `docs/visual_modernization_plan.md` record
  the research-to-change mapping.

## Still Out Of Scope

- ReliefWeb, EONET, FIRMS, NWS, USGS adapters
- Polygon/heatmap/wildfire/disaster overlays
- Tracker globe loaded-state visual fixtures
- New HUD CSS tokens or extra animation
