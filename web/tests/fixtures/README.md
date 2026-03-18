# Captured Globe Fixtures

These fixtures are reviewed, provenance-backed test artifacts for positive-path
globe visuals.

Rules:

- Do not hand-edit the JSON payloads.
- Do not replace them with mock, demo, synthetic, or "cleaned up" scene data.
- Capture from the real local FastAPI app contract and review the resulting
  provenance before committing.
- Keep raw local caches such as `data/intel_news.json` ignored; commit only the
  derived reviewed fixture under this directory when needed.

Regenerate the current intel globe fixture from repo root:

```powershell
python scripts/capture_globe_fixture.py --scene intel
cd web
npx playwright test tests/globe.visual.spec.ts --update-snapshots
```

Current fixture:

- `intel-globe.fixture.json` captures `/api/osint/scene/intel?industry=all`
  and `/api/intel/meta` through `fastapi.testclient`, with cache provenance
  recorded from `data/intel_news.json`.

Tracker note:

- `python scripts/capture_globe_fixture.py --scene tracker` is supported, but
  it intentionally fails closed unless the real tracker scene returns at least
  one point feature and one focus target.
- Do not commit a tracker fixture generated from an empty, fallback-only, or
  degraded scene.
