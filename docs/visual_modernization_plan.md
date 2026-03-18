# Visual Modernization Plan

Status: Proposed on March 17, 2026. Execution is gated by `docs/standards_remediation_plan.md`.

## Intent

Move Clear from a page/card-heavy data application into a globe-first intelligence surface where the world itself becomes the canvas for trackers, conflict, weather, news, cargo, and regional emotion signals.

This is not a pure styling pass. It is an architecture, data-contract, and interaction redesign that must preserve:

- deterministic analytics
- provenance and freshness
- CLI/API/web parity
- safe fallbacks when a richer visual layer is unavailable

## What The Audit Confirmed

### Frontend

- The current web stack already has useful primitives: `framer-motion`, `recharts`, `plotly.js`, `maplibre-gl`, and `leaflet`.
- The dominant pattern is still page-local cards, KPI tiles, collapsibles, and local fetch/state logic.
- `Trackers.tsx` already contains the strongest geo surface in the app, but it is too large and page-bound to serve as the shared scene foundation.
- `Surface3D.tsx` proves the app already has a fullscreen overlay pattern, but it is chart-specific rather than scene-specific.
- `AppShell.tsx` is the right insertion point for an immersive layer because it already owns global layout, drawers, and top navigation.

### Data Pipeline And CLI

- The tracker pipeline already has the most globe-ready data in the repo: points, history trails, replay windows, geofence events, speed/volatility heat signals, and shipping/aircraft categorization.
- Intel and news already contain useful geography, but much of it is region-level or inferred rather than true event geometry.
- The API already preserves provenance through `meta` payloads, which gives us a solid base for scene freshness, warnings, and lineage.
- The major blocker is not a complete lack of geo data. The blocker is the lack of one canonical geo scene contract shared by `modules`, `web_api`, the web app, and the CLI.

## Product Direction

The target experience should feel like an operating surface instead of a dashboard:

- a fullscreen, rotatable globe with glow, atmosphere, and depth
- floating controls that inherit the same color language as the globe
- filters that change what the globe renders instead of swapping to separate pages
- camera motion that can move between global overview, region focus, and entity follow mode
- replay and timeline controls that make movement and escalation understandable without narration-heavy explanations

The first implementation target should be OSINT, not the full app. OSINT already groups Trackers, Intel, and News and is the natural place to prove the interaction model.

On capable client hardware, the immersive globe should be the default presentation surface. Simpler fallbacks should exist for recovery, testing, degraded devices, and operational continuity, but they should not define the visual bar for meetings or client-facing walkthroughs.

## Researched Technology Direction

### Recommended Primary Stack

Use this as the core globe stack:

- `three`
- `@react-three/fiber`
- `@react-three/drei`
- `@react-three/postprocessing`

Reasoning:

- This gives the project full control over atmosphere, shaders, particle fields, camera choreography, interaction, and custom overlays.
- It fits the existing React app better than a separate GIS-style runtime.
- It supports the kind of immersive shell-level takeover the product direction needs.

Supporting stack:

- Keep `maplibre-gl` for 2D and local map fallback, tactical ground views, and lower-risk map experiences.
- Keep `plotly.js` for numeric surfaces that belong in reports and client analytics.
- Treat fallbacks as resilience and development paths, not the primary client presentation mode on capable machines.

### Secondary Tools To Use Selectively

- `react-globe.gl` is a strong spike/prototype option because its README already exposes points, arcs, polygons, hex bins, heatmaps, paths, labels, and tiles on top of a Three-based globe. It is a good fast-validation tool, but it should not define the final architecture.
- `deck.gl` is useful for data concepts like arc layers and H3-based aggregation, but `GlobeView` is explicitly marked experimental in the official docs and currently only supports `LNGLAT` coordinates, with unsupported pieces like `MVTLayer` and `TerrainExtension`. That makes it a poor choice for the primary immersive globe runtime.
- `CesiumJS` remains the reserve option if the product later requires terrain, 3D tiles, satellite-style Earth rendering, or deeper geospatial simulation. It is powerful, but heavier than what this repo needs for the first modernization pass.

### Research Links

- `@react-three/fiber` introduction: https://r3f.docs.pmnd.rs/getting-started/introduction
- `@react-three/fiber` scaling performance: https://r3f.docs.pmnd.rs/advanced/scaling-performance
- `react-postprocessing` introduction: https://react-postprocessing.docs.pmnd.rs/introduction
- `react-globe.gl` README: https://github.com/vasturiano/react-globe.gl
- `deck.gl GlobeView`: https://deck.gl/docs/api-reference/core/globe-view
- `deck.gl ArcLayer`: https://deck.gl/docs/api-reference/layers/arc-layer
- `deck.gl H3HexagonLayer`: https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer
- `MapLibre` globe projection example: https://maplibre.org/maplibre-gl-js/docs/examples/globe-spin/
- `MapLibre` custom Three.js layer example: https://maplibre.org/maplibre-gl-js/docs/examples/add-a-3d-model-using-threejs/
- `CesiumJS` quickstart: https://cesium.com/learn/cesiumjs-learn/cesiumjs-quickstart/
- `Playwright` visual comparisons: https://playwright.dev/docs/test-snapshots
- `MDN` `prefers-reduced-motion`: https://developer.mozilla.org/docs/Web/CSS/@media/prefers-reduced-motion

## Architectural Recommendation

### 1. Add A Shared Globe Scene Layer

Add a shell-level scene provider and overlay host under `web/src/components/layout/AppShell.tsx`.

This layer should own:

- globe open/close state
- current scene mode
- selected entity
- camera target and follow mode
- active layers and filters
- timeline position
- focus locks
- reduced-motion and fallback behavior

This is the structural change that lets the globe sit over the rest of the app while navigation, assistant, and context panels float above it.

### 2. Make OSINT The First Consumer

The first immersive route should be the OSINT workspace, with the ability to open the globe over:

- trackers
- conflict
- weather
- news and emotion
- cargo and logistics

OSINT is already the cleanest shared context for this work and avoids forcing a repo-wide redesign on day one.

### 3. Add Shared Geo Scene Contracts In `modules`

Create a shared module such as:

- `modules/market_data/scene_payloads.py`

It should expose three canonical payload shapes:

1. `GeoFeature`
   - `id`
   - `layer`
   - `geometry`
   - `ts`
   - `source`
   - `confidence`
   - `freshness`
   - `warnings`
   - `properties`

2. `GeoLayerPayload`
   - `id`
   - `kind`
   - `legend`
   - `filters`
   - `features`
   - `style_hints`
   - `time_bounds`
   - `meta`

3. `GeoScenePayload`
   - `scene_id`
   - `camera_defaults`
   - `timeline`
   - `layers`
   - `focus_targets`
   - `meta`

All new globe-capable API routes should return these shared contracts and only then attach route metadata in `web_api`.

### 4. Keep CLI/API/Web On The Same Data Source

Do not assemble globe-only data in React.

Instead:

- `modules` should build the canonical geo payloads
- `web_api` should validate and expose them
- the CLI should render summaries and exports from those same payloads
- the web scene should visualize those same payloads

That prevents the product from splitting into a “pretty web app” and a separate “real data” CLI.

## Layer Model

The globe should support these layer classes from the start:

- `point`
  - aircraft, ships, ports, airports, weather stations, conflict events
- `path`
  - tracker history, replay trails, movement breadcrumbs
- `arc`
  - routes, cargo lanes, geopolitical or market linkages
- `hex`
  - emotion intensity, disruption density, weather severity, article concentration
- `choropleth`
  - region- or country-level conflict and emotion fills
- `particle`
  - wind fields, storm flow, directional tension, traffic drift
- `label`
  - entity names, region callouts, dynamic event summaries

## Visual Primitives To Build

The first visual kit should include:

- atmosphere halo and transparent globe shell
- soft bloom and emissive edge lighting
- point pulses for live entities
- route arcs with motion trails
- hex-shell heat overlays for regional intensity
- conflict and emotion regional glow layers
- weather particle fields and storm band overlays
- timeline scrubber and replay controls
- camera bookmarks for global, region, and entity-follow views

The aesthetic should stay restrained and tactical:

- dark base
- transparent structure
- glowing data
- floating controls
- no flat spreadsheet-like surfaces as the primary experience

## Data Work Required Before The Globe Can Be Honest

### Trackers

Already strong enough for MVP:

- aircraft and ships
- category filtering
- history
- replay
- geofence events
- cargo-like categories

Still needed:

- explicit route arc builders
- airport and port anchors
- cargo lane metadata
- lane confidence and freshness

### News And Emotion

Already available:

- regions
- industries
- tags
- categories
- sentiment
- emotion counts

Still needed:

- region confidence for inferred geography
- conversion from article lists to scene layers
- H3 or region-cell aggregation for heat rendering
- explicit freshness semantics per derived overlay

### Conflict

Already available:

- region-based reporting
- article-driven theme extraction
- impact summaries

Still needed:

- direct event geometry where possible
- polygon or cell-based risk overlays
- clear distinction between inferred regional signal and true geocoded event data

### Weather

Current limitation:

- weather is fetched from a single centroid per region, which is not enough for true globe weather layers

Needed next:

- gridded or multi-point regional sampling
- raster or cell aggregation output
- wind vector support for particle overlays
- explicit coverage metadata so low-resolution weather does not pretend to be global precision

## Specialist Tracks

### 1. Frontend Scene Architect

Owns:

- `AppShell` overlay host
- OSINT globe entry
- scene provider
- camera model
- input and pointer-event handling

### 2. Geo Data Engineer

Owns:

- `GeoFeature`
- `GeoLayerPayload`
- `GeoScenePayload`
- layer builders for trackers, news, conflict, weather, and cargo
- provenance and freshness semantics

### 3. Motion And Experience Designer

Owns:

- atmosphere, lighting, motion language, focus transitions, reduced-motion strategy

### 4. CLI/API Parity Engineer

Owns:

- shared payload reuse
- export parity
- route validation
- metadata and warnings consistency

### 5. Performance And QA Hardening

Owns:

- bundle impact
- mobile degradation path
- fallback behavior
- Playwright globe smoke tests
- frame-rate and memory regression checks

## Phased Rollout

### Phase 0: Architecture Spike

Goal:

- prove the shell-level globe takeover and control model without rewriting the whole app

Deliver:

- `AppShell` overlay host
- OSINT-only globe toggle
- prototype globe with rotation, zoom, atmosphere, and floating controls
- one live tracker point layer

Exit criteria:

- the globe can fully take over the screen
- the user can rotate, zoom, and close it cleanly
- floating UI remains usable above the canvas

### Phase 1: Shared Scene Contracts

Goal:

- unify geo data before adding more visuals

Deliver:

- shared scene payload module in `modules/market_data`
- tracker adapters into scene payloads
- weather, conflict, and news scene layer adapters
- API route contract tests

Exit criteria:

- the same scene payload can be consumed by CLI, API, and web

### Phase 2: OSINT Globe MVP

Goal:

- make the globe genuinely useful, not decorative

Deliver:

- aircraft and ship markers
- history trails and replay
- regional emotion/conflict heat overlays
- weather severity layer
- layer filters and timeline scrubber
- provenance and freshness badges

Exit criteria:

- a user can explain current activity by rotating the globe and filtering layers, without depending on a separate table-first workflow

### Phase 3: Logistics And Cargo Expansion

Goal:

- deepen operational value

Deliver:

- cargo routes and shipping lanes
- airport and port pulses
- dwell and chokepoint overlays
- route health and disruption states

### Phase 4: Reports, Clients, And Executive Views

Goal:

- connect the new visual system to client-facing and report workflows

Deliver:

- report snapshots derived from the globe scene
- saved globe views
- client/account region overlays
- export packs with scene metadata

## Risks And Controls

### Risk: The Globe Becomes Pure Theater

Control:

- do not render a layer unless it has provenance, freshness, and clear semantics

### Risk: React/UI And Data Contracts Drift Apart

Control:

- build the geo contracts in `modules`, not in `web/src`

### Risk: Performance Regressions

Control:

- lazy-load globe code
- keep a 2D fallback path
- set frame-rate and bundle budgets before feature sprawl

### Risk: Region Inference Looks More Precise Than It Is

Control:

- display confidence and coverage
- visually distinguish inferred regional overlays from true event geometry

### Risk: The Existing Tracker Page Blocks Reuse

Control:

- extract tracker state, layer transforms, and focus logic into shared hooks before large globe expansion

## Testing And Hardening Expectations

- unit tests for scene payload builders
- API contract tests for every new layer route
- Playwright smoke tests for globe open, rotate, filter, and close
- regression tests for reduced-motion and fallback mode
- explicit stale-data and auth-error tests for globe overlays

### Additional Research Notes For Phase 0 Hardening

- The current `@react-three/fiber` performance guidance favors adaptive quality instead of assuming one fixed render cost. For this repo, that means using Canvas performance controls and a measured quality ramp before adding heavier layers.
- Playwright visual comparisons are viable for the globe, but only after non-essential motion is paused. Its screenshot animation controls stabilize DOM/CSS animation, not the WebGL render loop by themselves.
- Reduced-motion handling should be part of the globe architecture, not a later accessibility patch. The `prefers-reduced-motion` media feature is the right contract for disabling auto-rotation, pulse effects, and other non-essential motion while keeping the scene readable.

Phase 0.5 hardening should therefore include:

1. reduced-motion support for the immersive globe and floating overlay controls
2. adaptive render quality for the Three scene before additional heatmaps or particle layers land
3. a dedicated Playwright visual regression spec with committed overlay screenshots for baseline and manipulated globe states
4. persistent scene state so scope and camera presets survive close/reopen cycles during demos

### Phase 0.75 Progress Note

The first non-tracker immersive layer should be a centroid-based regional intel scene, not a fake polygon/heatmap pass. The repo now has the right ingredients for that move:

- existing `REGIONS` centroids in `modules/market_data/intel.py`
- fused regional weather/conflict/news scoring that can be surfaced with provenance warnings
- a second immersive scene route at `/api/osint/scene/intel`
- scene-aware HUD controls so tracker scope and regional intel lenses are not mixed together
- Playwright smoke plus visual regression coverage for a manipulated intel-globe state

This is intentionally not the final visual form for weather/conflict/news. It is a truthful intermediate step that turns existing regional intelligence into globe-native nodes while making the representational limits explicit:

- weather remains sampled from representative regional coordinates
- conflict remains regional signal density, not exact event geocodes
- news/emotion remains headline classification, not article-level location truth

### Phase 0.85 Performance Guardrail Note

Before moving into denser animation and UI choreography, the frontend now has a stronger bundle boundary model:

- route-level lazy loading keeps non-active pages out of the initial shell
- OSINT tab panels lazy-load by tab and prewarm on hover/focus
- globe, charts, markdown, Leaflet, and shared React/runtime code now sit in more predictable async/vendor chunks
- Leaflet fallback code is deferred until the fallback path is actually needed
- local bundle verification now exists through `web/scripts/check-bundle.mjs`

Current measured direction is much healthier than the pre-pass state:

- the initial shell JS dropped from roughly 1.19 MB to roughly 44.7 kB plus a 48.3 kB React vendor chunk
- tracker/intel/news/report/system workspaces now load on demand
- heavy async visual domains remain intentionally separate:
  - globe vendor ~930 kB
  - Plotly ~4.8 MB

That means the next visual phase should treat bundle budgets as a design constraint, not a later cleanup item.

### Phase 0.9 Intel Contract Correction Note

The next blocker was not rendering polish. It was an upstream intel-contract
error that made the globe and Intel page undercount real conflict/disruption
coverage.

Root cause now recorded:

- RSS enrichment was classifying on article titles only, which missed explicit
  conflict/weather/scarcity context that often appears in feed summaries.
- Region inference was too sparse for real theaters like Ukraine/Russia ->
  Europe and Iran/Israel/Yemen -> Middle East.
- Conflict/news context was overloaded into one mixed category bucket, which
  made `conflict` counts look empty even when the article set was clearly about
  war, strikes, shortages, or infrastructure attacks.
- The earlier GDELT regional query shape relied on `sourcecountry` fragments
  that were not grounded for multi-word repo regions.

Phase 0.9 corrected that by moving the shared contract to:

- title-plus-summary deterministic classification
- explicit `event_tags`, `event_counts`, `impact_channels`, and
  `impact_counts`
- broader reviewed event coverage for conflict, disruption, scarcity,
  disaster, sanctions, and infrastructure
- broader reviewed region aliases for key active theaters
- a centroid-based hotspot pulse layer for the globe that is clearly presented
  as a regional highlight, not exact incident geometry
- region and industry emotion rollups surfaced in the Intel page and selected
  globe-region detail

What is still intentionally not claimed:

- hotspot pulses are not country polygons or incident footprints
- weather remains representative-coordinate meteorology, with news-derived
  weather context kept separate from observed meteorological inputs
- article geography is still region-scoped text classification, not article
  geocoding truth

Specialist tracks now required before full area fills:

1. Event-taxonomy specialist: continue widening reviewed term coverage and add
   provenance-backed captured fixtures so category drift can be caught without
   fabricated positive-path data.
2. Geo-intel specialist: evaluate GDELT GEO 2.0 plus other reviewed open
   geospatial sources for truthful country/region overlays, wildfire feeds, and
   future non-centroid hotspot geometry.
3. UX/visual systems specialist: evolve centroid pulses into layered area
   visuals only after real polygons or reviewed display extents exist.
4. Browser verification specialist: keep visual baselines on settled states and
   continue replacing invented positive-path browser assertions with real local
   or provenance-backed fixtures.

Primary research references used for this correction and the next step:

- GDELT DOC 2.0 API:
  https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- GDELT GEO 2.0 API:
  https://blog.gdeltproject.org/gdelt-geo-2-0-api-debuts/
- spaCy rule-based matching:
  https://spacy.io/usage/rule-based-matching
- spaCy EntityRuler:
  https://spacy.io/api/entityruler
- Open-Meteo API docs:
  https://open-meteo.com/en/docs

## Immediate Next Move

With the architecture spike and hardening slice in place, the next move is:

1. Add provenance-backed captured fixtures for Intel/globe positive-path visual
   checks so we can validate loaded hotspot/emotion states without fabricated
   scene data.
2. Evaluate reviewed open geospatial inputs for exact wildfire/disaster and
   country/region overlays before any polygon-style fill work lands.
3. Add cargo/logistics and regional news/conflict/weather adapters on top of
   the corrected `GeoScenePayload` contract.
4. Reuse the same scene payloads for CLI summaries and exports.
5. Keep new animation work inside the bundle guardrails and revisit async chunk
   composition before layering on denser heatmaps, particle fields, or
   additional 3D chart packages.
