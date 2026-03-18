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

## Notes
- Browser tests now run against the real local API stack defined in `web/playwright.config.ts`; they should not rely on `?demo=true`, mock runtime data, or fabricated positive-path product flows.
- Destructive System-page browser coverage is currently limited to confirmation and fail-safe/error handling until the isolated standards-compliant test harness in `docs/standards_remediation_plan.md` is complete.
- Results land in `web/test-results/`.
- Bundle guardrails can be checked after a build with `npm run bundle:check`.
