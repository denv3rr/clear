# Tests

Pytest suite for the core runtime, API, and analytics utilities.

## Run
```powershell
python -m pytest
```

## Coverage highlights
- Client store integrity and migrations (`test_client_store_*`).
- Analytics math and models (`test_financial_calculations.py`,
  `test_regime_models.py`).
- Launchers and startup behavior (`test_clearctl_startup.py`,
  `test_launcher_utils.py`).
- News/intel filtering and scoring (`test_intel_*`, `test_news_collectors.py`).

## Notes
- Add new tests alongside the feature they validate.
- Keep tests deterministic and data-driven (no randomization).
