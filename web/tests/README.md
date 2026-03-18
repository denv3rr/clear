# Web Tests

Playwright end-to-end tests for the web UI.

## Run
```powershell
npm run test:e2e
```

## Visual
```powershell
npm run test:e2e:visual
```

- Globe visual baselines live next to their spec in `web/tests/globe.visual.spec.ts-snapshots/`.
- Visual checks use reduced-motion mode so the immersive overlay can be snapshotted deterministically.
- Positive-path globe visuals now use reviewed captured fixtures from `web/tests/fixtures/`, not invented route stubs.
- Refresh the intel loaded-state fixture from repo root with `python scripts/capture_globe_fixture.py --scene intel`, then update snapshots with `cd web` and `npx playwright test tests/globe.visual.spec.ts --update-snapshots`.
- Tracker fixture capture is available through `python scripts/capture_globe_fixture.py --scene tracker`, but it will fail closed until a real non-empty tracker scene is available.

## Notes
- Browser tests now run against the real local API stack defined in `web/playwright.config.ts`; they should not rely on `?demo=true`, mock runtime data, or fabricated positive-path product flows.
- The current captured positive-path fixture covers the intel globe loaded state. Tracker loaded-state visuals still need a reviewed capture path before they should replace fail-safe-only browser checks.
- Destructive System-page browser coverage is currently limited to confirmation and fail-safe/error handling until the isolated standards-compliant test harness in `docs/standards_remediation_plan.md` is complete.
- Results land in `web/test-results/`.
- Bundle guardrails can be checked after a build with `npm run bundle:check`.
