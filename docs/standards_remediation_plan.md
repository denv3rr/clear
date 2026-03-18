# Standards Remediation Plan

This plan is the mandatory gate before the next major visual modernization
phase. `docs/us_gov_standards.md` remains the binding baseline; this document
turns the audit findings into ordered engineering work, owners, and exit
criteria.

## Audit Snapshot

Audit date: 2026-03-17

Closed in the current pass:
- Removed runtime/demo mock plumbing from the web data layer and tracker stream.
- Removed browser `?demo=` happy paths and moved Playwright to the real local
  API/UI stack.
- Rebased globe visual regression on fail-safe unavailable states instead of
  fabricated scene content.
- Removed heuristic assistant confidence values from runtime assistant output
  and exports.
- Removed heuristic confidence labels from weather/conflict/combined intel
  reports; those reports now expose support/availability instead of invented
  certainty labels.
- Replaced the Yahoo macro snapshot `fake_ts` shortcut with an explicit
  empty-result backoff window.
- Removed the tracker map demo-tile fallback and restored MapLibre as the
  primary tracker map path with explicit failure behavior.
- Renamed the aggregate portfolio history helper so it no longer mislabels
  real-data reconstruction as "synthetic."
- Replaced random-data unit tests with deterministic sequences for regime and
  financial calculations.
- Replaced a silent startup schema failure with explicit logging plus startup
  failure, and made `.env` load issues visible in logs.

Still open:
- Many Python tests still rely on synthetic in-memory payloads or monkeypatched
  positive-path data instead of live local data or captured real fixtures with
  provenance.
- Positive-path browser mutation tests still need an isolated real-data harness
  so we can verify destructive flows without touching local operator data.
- New immersive Intel/globe positive-path visuals now need provenance-backed
  captured fixtures so hotspot/emotion loaded states can be verified without
  fabricating scene payloads.
- Widespread `except Exception` and bare `pass` usage still needs a structured
  fail-safe audit across `modules/`, `web_api/`, and startup code.
- Some report/export tests still use invented `confidence` strings in fixture
  payloads even though runtime behavior is moving away from them.

## Specialist Roles

- Standards Lead: owns interpretation of `docs/us_gov_standards.md`, blocks
  work that violates the baseline, and signs off on phase exits.
- Data Provenance Engineer: tracks source, timestamp, lineage, fixture capture,
  and payload metadata across API, CLI, and exports.
- Backend Safety Engineer: audits fail-open behavior, exception handling,
  schema validation, startup guarantees, and destructive-route safeguards.
- Frontend Accessibility Engineer: owns Section 508 behavior, reduced-motion,
  keyboard/focus paths, and non-canvas control parity for immersive views.
- Browser Verification Engineer: converts Playwright to real-data or
  provenance-backed fixtures, maintains visual baselines, and blocks fabricated
  happy paths.
- Analytics Integrity Engineer: removes heuristic confidence/math shortcuts,
  adds methodology blocks, and ensures deterministic formulas are documented.
- Visual Systems Engineer: advances the globe/UI work only after the standards
  gate stays green, and keeps bundle/render budgets measured.

## Phase 0: Standards Closure Gate

Objective: remove the most direct contradictions before new product surface
area is added.

Tasks:
- Remove demo/mock/synthetic runtime paths from shared product code.
- Eliminate browser demo query params and fabricated positive-path responses.
- Replace random-data unit tests with deterministic inputs.
- Replace silent startup/schema failures with explicit logging and safe stop
  behavior.
- Remove heuristic certainty labels where the app cannot defend them.

Exit criteria:
- No runtime product code depends on demo/mock data loaders.
- Playwright smoke/assistant/system/globe suites run against the real local
  stack or explicit negative-path failure checks only.
- The affected Python and Playwright suites pass.

## Phase 1: Verified Test Data Infrastructure

Objective: give the repo a compliant way to test positive paths without
inventing business data.

Tasks:
- Build a captured-fixture format that stores source, timestamp, capture
  method, and schema version.
- Add an ephemeral SQLite/API harness for browser tests that need destructive
  or workflow-heavy positive paths.
- Split browser tests into:
  - real local data tests
  - captured real-fixture tests
  - negative-path validation tests
- Ban new positive-path route stubs that fabricate successful business data.

Exit criteria:
- System/browser mutation tests no longer need fabricated success bodies.
- New fixtures carry provenance metadata and are reviewable artifacts.
- Test docs explain when live local data vs captured fixtures are allowed.

## Phase 2: Fail-Safe And Silent-Failure Audit

Objective: remove quiet failure behavior that can hide corruption or weaken
guarantees.

Tasks:
- Audit `except Exception` and bare `pass` usage across startup, data loads,
  view models, feeds, and reporting.
- For each case, choose one of:
  - explicit log + safe degraded state
  - explicit log + startup failure
  - typed exception handling
  - removal of dead fallback branch
- Add tests for the corrected failure mode.

Exit criteria:
- Silent failures are documented exceptions, not defaults.
- Startup-critical paths fail closed when integrity checks fail.
- Degraded states are explicit in UI/API payloads.

## Phase 3: Analytics And Report Output Remediation

Objective: make user-facing analytics defensible to customers, auditors, and
internal reviewers.

Tasks:
- Remove or rename heuristic `confidence` outputs that are really coverage or
  source-availability signals.
- Add methodology blocks for derived metrics, risk scores, and report sections.
- Keep probability/confidence outputs only where the value is a real model
  output with documented inputs and units.
- Update report/export helpers and tests so they no longer normalize invented
  certainty labels by default.

Exit criteria:
- User-facing reports do not claim unsupported certainty.
- Every retained metric or probability has inputs, window, units, and source.
- Report/export tests align with the runtime contract.

## Phase 4: Visual Foundation Re-Entry

Objective: resume visual modernization on a compliant base.

Tasks:
- Keep globe/UI work behind measured bundle and render budgets.
- Require provenance/freshness badges for new immersive layers.
- Keep reduced-motion and non-canvas controls first-class.
- Expand visual regression only for settled, reviewable states.

Exit criteria:
- No new globe layer ships without provenance, freshness, and performance
  verification.
- Visual tests validate real or fail-safe states, not invented presentation
  scenes.

## Phase 5: Globe Expansion

Objective: continue the immersive roadmap without reintroducing standards
debt.

Tasks:
- Add cargo/logistics, weather, conflict, and news layers via the shared geo
  scene contract.
- Build saved scene/filter presets for presentation workflows.
- Add report/export parity for globe states.
- Keep fallbacks as resilience paths, not the default client surface.

Exit criteria:
- New layers consume canonical geo scene payloads.
- Presentation flows preserve provenance, warnings, and freshness.
- Bundle and frame budgets remain inside guardrails.

## Release Gate

Before any future visual phase is marked complete:
- The active specialists have re-skimmed `docs/us_gov_standards.md`.
- The touched phase checklist in this file is updated.
- The relevant Python and Playwright suites pass.
- No new fabricated positive-path data was added.
- Any remaining standards debt is listed explicitly in `AGENTS.md` and not
  hidden inside TODOs.
