# Inspection role checklists

Use these checklists only after loading `docs/inspection/corpus.json`.
Each role is an independent verifier. Do not collapse roles into a single
self-review by the authoring agent.

The roles match `docs/standards_remediation_plan.md`. They do not create
new product specialists or a multi-agent runtime.

## standards-lead

- [ ] The change cites `docs/us_gov_standards.md` as the winning baseline.
- [ ] No new workflow, framework, or certification claim was invented.
- [ ] Globe Phase 2 implementation was not started unless Phase 1 and
      Phase 2 remediation exits have evidence.
- [ ] Git path matches `docs/agent_git_standards.md` (branch type, secrets,
      no ignored agent files).
- [ ] Remaining standards debt is listed explicitly, not hidden in TODOs.

## data-provenance

- [ ] Shared payloads keep source, timestamp, warnings, and lineage.
- [ ] New fixtures include capture method, schema version, and review notes.
- [ ] Missing data is unavailable or degraded, not filled.
- [ ] Geometry truth level is labeled when coordinates or overlays are shown.
- [ ] Operator runtime files under `data/` were not committed.

## backend-safety

- [ ] Auth, schema, and startup failures fail closed or degrade explicitly.
- [ ] Destructive routes still require confirmation.
- [ ] New `except Exception` / bare `except` / silent `pass` did not appear
      unless the scanner baseline was updated with a classified reason.
- [ ] Typed exceptions were preferred over broad catches.
- [ ] Isolated tests do not write operator SQLite files.

## frontend-accessibility

- [ ] Keyboard access, focus, and labels still work on touched UI.
- [ ] Reduced-motion paths were not removed.
- [ ] Canvas-heavy views still expose non-canvas controls and state.
- [ ] Color is not the only encoding for status or conflict.

## browser-verification

- [ ] No fabricated positive-path browser bodies or `?demo=` hooks.
- [ ] Playwright uses the real local stack, a reviewed captured fixture, or
      an explicit negative-path check.
- [ ] Destructive browser flows were not added without the isolated harness.
- [ ] Globe snapshots were not updated from invented scene data.

## analytics-integrity

- [ ] Metrics keep inputs, formula, units, window, and source.
- [ ] No placeholder confidence, random walks, or filler series.
- [ ] Assistant/report `confidence` remains null unless a documented scoring
      contract exists.
- [ ] Calculation changes have tests in the Python suite.

## visual-systems

- [ ] No new dense globe layer shipped without provenance, freshness, and
      performance evidence.
- [ ] Bundle/frame budgets in `web/scripts/check-bundle.mjs` still pass.
- [ ] Fallbacks remain resilience paths, not the default presentation.
- [ ] Visual modernization did not jump the standards gate.
