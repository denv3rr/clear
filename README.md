<div align="center">

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Top Language](https://img.shields.io/github/languages/top/denv3rr/clear)
![Repo Size](https://img.shields.io/github/repo-size/denv3rr/clear)
![GitHub Created At](https://img.shields.io/github/created-at/denv3rr/clear)
![Last Commit](https://img.shields.io/github/last-commit/denv3rr/clear)
![Issues](https://img.shields.io/github/issues/denv3rr/clear)
![Website](https://img.shields.io/website?url=https%3A%2F%2Fseperet.com&label=seperet.com)

  <a>
    <!--
    <img src="assets/welcome_screen_1.png" alt="Screenshot" style="width=50%">
    -->
  </a>
</div>

<div align="center">
  <a href="https://seperet.com">
    <img width="100" src="https://github.com/denv3rr/denv3rr/blob/main/IMG_4225.gif" />
  </a>
</div>

<br></br>

<div align="center">

[Overview](#overview) •
[Quick Start](#quick-start) •
[Configuration](#configuration) •
[Stack](#stack) •
[Data Sources](#data-sources) •
[Financial Methods](#financial-methods) •
[Sources Index](#sources-index) •
[Disclaimer](#disclaimer)

</div>

---

> [!WARNING]
> Work in progress.

## Overview

A portfolio management, analytics, and global tracking platform with SQLite-backed client storage and JSON import/export.

## Features

- Client and account management (DB-backed; JSON export/import)
- Portfolio analytics + regime/pattern modeling
- Market dashboard with macro snapshots + map fallback
- Global flight and maritime tracking (OpenSky-only)
- Intel and news aggregation with filters
- Diagnostics + system health views
- Reports and exports (CLI + web)
- Web API + WebSocket streaming trackers

<details>
<summary><strong>More Details</strong></summary>
<br>
  
**Some features still under development**
  
- Lot-aware holdings and position-level analysis
- Regime transition matrices, CAPM, and derived analytics
- Multi-interval views with paging and cached snapshots
- Tracker heat/volatility metrics and relevance tagging
- Weather and conflict reporting with caching and exports
- Health-aware sources with retry/backoff handling
- AI assistant endpoint (draft) for deterministic summaries

</details>

<!--
## Screenshots

<br>

<img src="assets/welcome_screen_1.png" alt="Welcome Screen" width="70%" />
-->

## Quick Start

```pwsh
git clone git@github.com:denv3rr/clear.git --depth 1
cd clear
python clearctl.py start
```

## Web App (API + UI)

```pwsh
python clearctl.py start
python clearctl.py stop
```

If npm is not found, install Node.js first (includes npm) and retry:

- Windows (winget): `winget install OpenJS.NodeJS.LTS`
- Windows (scoop): `scoop install nodejs-lts`
- macOS: `brew install node`
- Linux: https://nodejs.org/en/download/package-manager

<!--
## Demo (GitHub Pages)

The web demo uses deterministic mock data and hash routing for GitHub Pages.

```pwsh
cd web
VITE_DEMO_MODE=true VITE_HASH_ROUTER=true VITE_BASE=/ npm run build
```

For project pages (non-user pages), set `VITE_BASE=/clear/` to match the repo name.

The workflow deploys via `GH_PAGES_TOKEN`, which must be stored as a repository
secret in this repo with `public_repo` (or full `repo`) scope. The destination
repo (`denv3rr/denv3rr.github.io`) should have Pages set to the `main` branch
root.
-->

## Launcher Commands

```pwsh
# Start API + web UI (foreground; Ctrl+C stops)
python clearctl.py start

# Start API only (no web UI)
python clearctl.py start --no-web

# Start the web stack (API + UI)
python clearctl.py web

# Start the CLI
python clearctl.py cli

# Run in background
python clearctl.py start --detach

# Stop background services
python clearctl.py stop

# Status + health
python clearctl.py status

# Logs (last 200 lines)
python clearctl.py logs

# Doctor (deps + port + health checks)
python clearctl.py doctor
```

Convenience wrappers:

- Windows PowerShell: `.\clear.ps1 start`
- macOS/Linux: `./clear.sh start`
- Windows PowerShell: `.\clear.ps1 web` / `.\clear.ps1 cli`
- Windows CMD: `clear web` / `clear cli`
- macOS/Linux: `./clear web` / `./clear cli`

Service templates for always-on usage: `docs/platform_services.md`

## Local Reports (Offline)

Generate a client report without any model installed:

```pwsh
python -m modules.reporting.cli --client-id <CLIENT_ID> --format md
```

Optional output file:

```pwsh
python -m modules.reporting.cli --client-id <CLIENT_ID> --format md --output data/client_weekly_brief.md
```

  Health check:

  ```pwsh
  python -m modules.reporting.cli --health-check
  ```

  Startup safety checks:
  - `run.py` performs a syntax compile pass across core modules and warns if `config/settings.json` is invalid JSON.
  - `run.py` warns if `data/clients.json` exists and fails schema checks (legacy import/export file).
  - Legacy lot timestamps are normalized to ISO-8601 on startup (and can be forced via Settings -> Diagnostics -> Normalize Lot Timestamps).
  - The API bootstraps `data/clients.json` into `data/clear.db` on startup, merging missing entries without overwriting existing rows.

### Local Model Setup

> [!NOTE]
> Incomplete

For model-enhanced reports, install Ollama (recommended) or run a local HTTP server (llama.cpp, vLLM) and run with `--use-model`:

```pwsh
python -m modules.reporting.cli --client-id <CLIENT_ID> --format md --use-model --model-id llama3
```

Install instructions:

- Windows (Scoop): `scoop install ollama`
- macOS (Homebrew): `brew install ollama`
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`

Local HTTP servers:
- llama.cpp server with OpenAI-compatible endpoints (`/v1/chat/completions`)
- vLLM or similar local endpoint

## Testing

```pwsh
# Run all tests
python -m pytest
```

Web smoke tests (requires Node/npm):

```pwsh
cd web
npm install
npx playwright install
npm run test:e2e
```

Optional: validate Playwright browsers via the launcher:

```pwsh
python clearctl.py doctor --web-tests
```

## Configuration

### Finnhub API Key

Although the basic Finnhub.io service is free, some international exchanges require a paid plan.

1. Create a free account: https://finnhub.io/register
2. Get your API key: https://finnhub.io/dashboard
3. Copy `.env.example` to `.env`
4. Add your key:

```bash
# API KEYS
FINNHUB_API_KEY=your_api_key_here
```

> [!WARNING]
> Do not commit any `.env` files.

### Web API Key (Optional)

If you set `CLEAR_WEB_API_KEY`, the API enforces `X-API-Key` on all routes and
the launcher forwards it to the UI as `VITE_API_KEY` for local auth.

```bash
CLEAR_WEB_API_KEY=your_local_key
```

### Environment Variables

OpenSky is the only flight feed right now; configure OAuth credentials in `.env` for new accounts (legacy basic auth still works for older accounts).

| Variable | Purpose | Used By |
| --- | --- | --- |
| `FINNHUB_API_KEY` | Enables Finnhub symbol/quote lookups. | Market Feed, Settings |
| `OPENSKY_CLIENT_ID` | OpenSky OAuth client id (new accounts). | Global Trackers |
| `OPENSKY_CLIENT_SECRET` | OpenSky OAuth client secret (new accounts). | Global Trackers |
| `OPENSKY_USERNAME` | OpenSky basic auth username (legacy accounts). | Global Trackers |
| `OPENSKY_PASSWORD` | OpenSky basic auth password (legacy accounts). | Global Trackers |
| `OPENSKY_BBOX` | OpenSky bounding box (`minLat,minLon,maxLat,maxLon`). | Global Trackers |
| `OPENSKY_EXTENDED` | Request OpenSky category metadata (`1`/`0`). | Global Trackers |
| `OPENSKY_ICAO24` | Comma-separated ICAO24 filter list. | Global Trackers |
| `OPENSKY_TIME` | Unix timestamp to request historical state vectors. | Global Trackers |
| `SHIPPING_DATA_URL` | Shipping feed endpoint for vessel tracker. | Global Trackers |
| `CLEAR_INCLUDE_COMMERCIAL` | Include commercial flights when set to `1` (default off). | Global Trackers |
| `CLEAR_INCLUDE_PRIVATE` | Include private flights when set to `1` (default off). | Global Trackers |
| `CLEAR_GUI_REFRESH` | GUI tracker refresh seconds (default `10`). | GUI Tracker |
| `CLEAR_GUI_PAUSED` | Start GUI tracker paused when `1`. | GUI Tracker |
| `CLEAR_WEB_API_KEY` | Enforces API key auth + forwards to UI as `VITE_API_KEY`. | Web API, Web UI |

Flight operator metadata can be extended by copying `config/flight_operators.example.json` to `config/flight_operators.json`.

### AI Assistant (Draft)

The assistant module is in progress. The API endpoint (`/api/assistant/query`) currently supports a limited rules-based summarizer; unsupported modes/questions return a 501 response with an explicit "not implemented" payload and `meta` warnings. UI/CLI chat surfaces are planned. See `docs/ai_assistant.md` for the draft plan.

### AI Synthesis (Reports)

Report synthesis is configured in `config/settings.json` under the `ai` key:

  | Key | Purpose | Default |
  | --- | --- | --- |
  | `reporting.ai.enabled` | Toggle report model usage. | `true` |
  | `reporting.ai.provider` | `auto`, `ollama`, `local_http`, or `rule_based`. | `auto` |
  | `reporting.ai.model_id` | Local model identifier. | `llama3` |
  | `reporting.ai.endpoint` | Local HTTP LLM endpoint for `/v1/chat/completions`. | `http://127.0.0.1:11434` |
  | `reporting.ai.timeout_seconds` | Per-request timeout in seconds. | `15` |

  The top-level `ai.*` settings remain for other synthesis features; reporting reads `reporting.ai` first and falls back to `ai.*` if missing.

### Tools Settings

Tools settings live in `config/settings.json` under the `tools` key:

  | Key | Purpose | Default |
  | --- | --- | --- |
  | `tools.perm_entropy_order` | Permutation entropy order (m). | `3` |
  | `tools.perm_entropy_delay` | Permutation entropy delay (tau). | `1` |

  These can be adjusted in Settings -> Tools.
  Tools interval selection persists per client; change it from the Tools menu when needed.

### Scroll Text Settings

Scroll text settings live in `config/settings.json` under `display.scroll_text`:

  | Key | Purpose | Default |
  | --- | --- | --- |
  | `display.scroll_text.prompt.speed` | Prompt scroll speed. | `8.0` |
  | `display.scroll_text.prompt.band_width` | Prompt highlight band width. | `3` |
  | `display.scroll_text.prompt.trail` | Prompt trail length. | `0` |
  | `display.scroll_text.prompt.highlight_style` | Prompt highlight style. | `bold bright_white` |
  | `display.scroll_text.prompt.base_style` | Prompt base style. | `dim` |
  | `display.scroll_text.warning.speed` | Warning scroll speed. | `8.0` |
  | `display.scroll_text.warning.band_width` | Warning highlight band width. | `3` |
  | `display.scroll_text.warning.trail` | Warning trail length. | `0` |
  | `display.scroll_text.warning.highlight_style` | Warning highlight style. | `bold bright_white` |
  | `display.scroll_text.warning.base_style` | Warning base style. | `dim` |

  These can be adjusted in Settings -> Display & UX -> Scroll Text.

### Runtime Files (Generated)

| Path | Purpose |
| --- | --- |
| `data/intel_news.json` | Cached RSS news items for reports. |
| `data/news_health.json` | RSS feed health + backoff state. |
| `data/ai_report_cache.json` | Cached AI synthesis outputs. |
| `data/clear.db` | Primary SQLite database for clients/accounts/holdings. |
| `data/clients.json` | Legacy import/export payload (auto-normalized when present). |
| `config/settings.json` | Runtime settings saved by the Settings module. |
| `data/*.md`, `data/*.csv`, `data/*.pdf`, `exports/`, `reports/` | Generated exports (ignored by git). |
| `.env`, `data/*.json`, `config/*local*.json` | Personal/runtime data (ignored by git). |

## Modules

- **Client Manager**: client profiles, accounts, holdings, lots, and tax settings
- **Market Feed**: macro dashboard, tickers, and interval switching
- **Financial Tools**: analytics, CAPM metrics, regime modeling
- **Settings**: API config, device info, preferences

## Stack

### Core Runtime

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-111827?style=for-the-badge&logo=qt&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-0F172A?style=for-the-badge&logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-111827?style=for-the-badge&logo=numpy&logoColor=white)
![Rich](https://img.shields.io/badge/Rich-121212?style=for-the-badge&logo=python&logoColor=white)
![Requests](https://img.shields.io/badge/Requests-0F172A?style=for-the-badge)
![HTTPX](https://img.shields.io/badge/HTTPX-0F172A?style=for-the-badge)
  ![python-dotenv](https://img.shields.io/badge/python--dotenv-111827?style=for-the-badge)
  ![psutil](https://img.shields.io/badge/psutil-111827?style=for-the-badge)
  ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-111827?style=for-the-badge&logo=sqlalchemy&logoColor=white)
  ![SQLite](https://img.shields.io/badge/SQLite-0F172A?style=for-the-badge&logo=sqlite&logoColor=white)
  ![Cryptography](https://img.shields.io/badge/Cryptography-0F172A?style=for-the-badge)

### Web Platform

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Uvicorn](https://img.shields.io/badge/Uvicorn-111827?style=for-the-badge)
![React](https://img.shields.io/badge/React-111827?style=for-the-badge&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-0F172A?style=for-the-badge&logo=typescript&logoColor=3178C6)
![React Router](https://img.shields.io/badge/React%20Router-1F2937?style=for-the-badge&logo=reactrouter&logoColor=CA4245)
![Node.js](https://img.shields.io/badge/Node.js-111827?style=for-the-badge&logo=node.js&logoColor=5FA04E)
![Vite](https://img.shields.io/badge/Vite-1A1B3A?style=for-the-badge&logo=vite&logoColor=646CFF)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-0F172A?style=for-the-badge&logo=tailwindcss&logoColor=38BDF8)
![React Markdown](https://img.shields.io/badge/React%20Markdown-111827?style=for-the-badge)
![Remark GFM](https://img.shields.io/badge/Remark%20GFM-0F172A?style=for-the-badge)
![Lucide](https://img.shields.io/badge/Lucide-111827?style=for-the-badge)

### Visualization

![MapLibre](https://img.shields.io/badge/MapLibre-0F172A?style=for-the-badge&logo=maplibre&logoColor=white)
![Leaflet](https://img.shields.io/badge/Leaflet-0B3D2E?style=for-the-badge&logo=leaflet&logoColor=white)
![Recharts](https://img.shields.io/badge/Recharts-1F2937?style=for-the-badge&logo=chartdotjs&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-111827?style=for-the-badge&logo=plotly&logoColor=white)
![TanStack Table](https://img.shields.io/badge/TanStack%20Table-161B22?style=for-the-badge&logo=reacttable&logoColor=white)
![Framer Motion](https://img.shields.io/badge/Framer%20Motion-0B0E13?style=for-the-badge&logo=framer&logoColor=white)

### Data Sources

  ![Finnhub](https://img.shields.io/badge/Finnhub-00C805?style=for-the-badge&logoColor=white)
  ![Yahoo Finance](https://img.shields.io/badge/Yahoo%20Finance-6001D2?style=for-the-badge&logo=yahoo&logoColor=white)
  ![OpenSky](https://img.shields.io/badge/OpenSky-111827?style=for-the-badge)
  ![Open-Meteo](https://img.shields.io/badge/Open--Meteo-0F172A?style=for-the-badge)
  ![GDELT](https://img.shields.io/badge/GDELT-111827?style=for-the-badge)
  ![RSS](https://img.shields.io/badge/RSS-0F172A?style=for-the-badge&logo=rss&logoColor=orange)

### Testing

![PyTest](https://img.shields.io/badge/PyTest-0F172A?style=for-the-badge&logo=pytest&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-0B0E13?style=for-the-badge&logo=playwright&logoColor=45BA4B)

## Data Sources

- **Finnhub**: symbols and quotes (optional - see [configuration](#configuration))
- **Yahoo Finance**: historical data and macro snapshots
- **OpenSky**: flight tracking feed (only source right now; OAuth for new accounts, legacy basic auth optional)
- **Open-Meteo**: weather signals for reports
- **GDELT**: conflict signals for reports (RSS fallback)
- **RSS News**: CNBC Top/World, MarketWatch, BBC Business (cached, health-aware)

## Financial Methods

<details>
<summary><strong>Formulas and references</strong></summary>

All formulas are shown in plain text for consistent rendering. Inline citations point to primary or canonical references.

### Core returns and risk metrics

| Metric | Formula | Notes | Source |
| --- | --- | --- | --- |
| Simple return | `r_t = (P_t / P_{t-1}) - 1` | Price-based simple return series. | [SEC glossary example](https://www.sec.gov/Archives/edgar/data/0000895421/000089542108000533/texassteel8kex991.htm) |
| Annualized mean | `mu_annual = mean(r) * A` | `A` inferred from timestamp spacing. | [CFA curriculum (return annualization)](https://www.cfainstitute.org/en/programs/cfa/curriculum) |
| Annualized volatility | `sigma_annual = std(r) * sqrt(A)` | Sample std with `ddof=1`. | [CFA curriculum (risk measures)](https://www.cfainstitute.org/en/programs/cfa/curriculum) |
| Sharpe ratio | `S = (mean(r_p) - r_f) / std(r_p)` | Uses annualized scaling. | [Investor.gov Sharpe](https://www.investor.gov/introduction-investing/investing-basics/terms-and-definitions/sharpe-ratio) |
| Sortino ratio | `S = (mean(r_p) - r_f) / std(r_p | r_p < r_f)` | Downside deviation uses returns below `r_f`. | [CFA curriculum](https://www.cfainstitute.org/en/programs/cfa/curriculum) |
| Max drawdown | `DD_t = (V_t / peak(V)) - 1`, `MDD = min(DD_t)` | Uses cumulative value series. | [CFA curriculum](https://www.cfainstitute.org/en/programs/cfa/curriculum) |
| Historical VaR | `VaR_q = quantile(r, 1 - q)` | Empirical quantile. | [Investor.gov VaR](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/understanding-value-risk) |
| CVaR (ES) | `CVaR_q = mean(r | r <= VaR_q)` | Tail average beyond VaR. | [Basel ES overview](https://www.bis.org/publ/bcbs265.pdf) |
| VaR 99% | `VaR_0.99 = quantile(r, 0.01)` | Historical 99% quantile. | [Investor.gov VaR](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/understanding-value-risk) |
| CVaR 99% | `CVaR_0.99 = mean(r | r <= VaR_0.99)` | 99% tail average. | [Basel ES overview](https://www.bis.org/publ/bcbs265.pdf) |
| EWMA volatility | `var_t = lambda * var_{t-1} + (1-lambda) * r_t^2` | Lambda defaults to 0.94. | [RiskMetrics 1996](https://www.msci.com/documents/10199/5915b101-4206-4ba0-aee2-3449d5c7e95a) |
| Concentration (HHI) | `HHI = sum(w_i^2)` | Used for sector concentration. | [Herfindahl-Hirschman Index](https://www.justice.gov/atr/herfindahl-hirschman-index) |

### Factor and benchmark metrics

| Metric | Formula | Notes | Source |
| --- | --- | --- | --- |
| Beta | `beta = cov(r_p, r_m) / var(r_m)` | Sample covariance and variance. | [CAPM (Sharpe 1964)](https://doi.org/10.2307/2977928) |
| CAPM expected return | `E[r_p] = r_f + beta * (E[r_m] - r_f)` | Used for alpha derivation. | [CAPM (Sharpe 1964)](https://doi.org/10.2307/2977928) |
| Alpha | `alpha = r_p - (r_f + beta * (r_m - r_f))` | Annualized using `A`. | [CAPM (Sharpe 1964)](https://doi.org/10.2307/2977928) |
| R-squared | `R2 = corr(r_p, r_m)^2` | Correlation of portfolio vs benchmark. | [CFA curriculum](https://www.cfainstitute.org/en/programs/cfa/curriculum) |
| Tracking error | `TE = std(r_p - r_b)` | Std of active returns. | [CFA curriculum](https://www.cfainstitute.org/en/programs/cfa/curriculum) |
| Information ratio | `IR = mean(r_p - r_b) / TE` | Active return per active risk. | [CFA curriculum](https://www.cfainstitute.org/en/programs/cfa/curriculum) |
| Treynor ratio | `T = (mean(r_p) - r_f) / beta` | Systematic-risk adjusted return. | [CFA curriculum](https://www.cfainstitute.org/en/programs/cfa/curriculum) |
| M2 (Modigliani) | `M2 = r_f + ((mean(r_p) - r_f) / std(r_p)) * std(r_m)` | Converts Sharpe to benchmark vol. | [CFA curriculum](https://www.cfainstitute.org/en/programs/cfa/curriculum) |

### Pattern and signal methods (toolkit suite)

| Method | Formula / Procedure | Interpretation | Source |
| --- | --- | --- | --- |
| FFT spectrum | `FFT(x_t - mean(x_t))` then power `\|X(f)\|^2` | Dominant cycle frequencies. | [DSP Guide (FFT)](http://www.dspguide.com/ch12.htm) |
| CUSUM change points | `S_t = max(0, S_{t-1} + x_t - mu - k)` | Flags shifts in mean. | [NIST/SEMATECH CUSUM](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm) |
| Motif similarity | `\|\|z_t - z_i\|\|_2` on rolling windows, where `z_t` and `z_i` are z-scored time series windows and `\|\| . \|\|_2` is the Euclidean distance. | Similar historical regimes identified by comparing shape and magnitude of z-scored windows. | [Time series motifs](https://www.cs.ucr.edu/~eamonn/Time_Series_Motifs.pdf) |
| Shannon entropy | `H = -sum(p_i * log2 p_i)` | Histogram-based return entropy; higher = more uniform outcomes, lower = concentrated outcomes. | [Shannon 1948](https://people.math.harvard.edu/~ctm/home/text/others/shannon/entropy/entropy.pdf) |
| Permutation entropy | `H = -sum(p_i * log2 p_i) / log2(m!)` | Ordinal pattern entropy (order m, delay tau); higher = more complex ordering. Toolkit uses m=3, tau=1. | [Bandt & Pompe 2002](https://doi.org/10.1103/PhysRevLett.88.174102) |
| Hurst exponent | `H = 2 * slope(log(lag), log(tau))` | <0.5 mean-revert, >0.5 trend. | [Hurst 1951](https://doi.org/10.1098/rspa.1951.0001) |

### Assumptions and data handling

- Returns use simple price returns; portfolio values are built from holdings and adjusted prices.
- Annualization factor `A` is inferred from average timestamp spacing (seconds per year / mean delta).
- Risk-free rate defaults to 4% annual for risk metrics unless a future config override is added.
- CAPM and regime models fall back to longer history when samples are insufficient; below thresholds the toolkit reports "Not Assessed".
- Pattern methods normalize series where required (mean-centering or z-scores) and enforce minimum window sizes.

### Validation

  - Toolkit metric tests live in `tests/test_toolkit_metrics.py`.
  - Market intel news filter tests live in `tests/test_intel_news_filters.py`.
  - Report synthesis tests live in `tests/test_report_synth.py`.
  - News emotion analysis filters to fresh items (default 4h) and ignores stale headlines.

</details>

## Sources Index

Metrics and modeling
- https://www.sec.gov/Archives/edgar/data/0000895421/000089542108000533/texassteel8kex991.htm
- https://www.cfainstitute.org/en/programs/cfa/curriculum
- https://www.investor.gov/introduction-investing/investing-basics/terms-and-definitions/sharpe-ratio
- https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/understanding-value-risk
- https://www.bis.org/publ/bcbs265.pdf
- https://www.msci.com/documents/10199/5915b101-4206-4ba0-aee2-3449d5c7e95a
- https://www.justice.gov/atr/herfindahl-hirschman-index
- https://doi.org/10.2307/2977928
- http://www.dspguide.com/ch12.htm
- https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm
- https://www.cs.ucr.edu/~eamonn/Time_Series_Motifs.pdf
- https://people.math.harvard.edu/~ctm/home/text/others/shannon/entropy/entropy.pdf
- https://doi.org/10.1103/PhysRevLett.88.174102
- https://doi.org/10.1098/rspa.1951.0001

Market data and platforms
- https://finnhub.io/
- https://finance.yahoo.com/
- https://open-meteo.com/
- https://www.gdeltproject.org/

News sources (current defaults)
- https://www.cnbc.com/
- https://www.marketwatch.com/
- https://www.bbc.com/business

Futures and derivatives references
- https://www.cmegroup.com/education.html
- https://www.theice.com/market-data
- https://www.lme.com/Metals/Market-data
- https://www.eurex.com/ex-en/markets
- https://www.cftc.gov/LearnAndProtect
- https://www.nfa.futures.org/investors/

Rates and macro references
- https://fred.stlouisfed.org/
- https://www.treasury.gov/resource-center/data-chart-center/interest-rates

<br><br>
<a href="https://seperet.com">
    <img src="https://user-images.githubusercontent.com/74038190/212284100-561aa473-3905-4a80-b561-0d28506553ee.gif">
</a> 

## Disclaimer

All content is provided **'as is'** without warranty; users should consult with a qualified professional before making any investment or financial decisions.

This project is for **informational use** and does not provide financial, legal, or tax advice.

No information presented should be construed as an offer to buy or sell securities. **The author assumes no liability for financial losses or decisions made based on the contents of this project**.

<br><br>
<a href="https://seperet.com">
    <img src="https://user-images.githubusercontent.com/74038190/212284100-561aa473-3905-4a80-b561-0d28506553ee.gif">
</a> 
<div align="center">
  <a href="https://seperet.com">
    <img width="100" src="https://github.com/denv3rr/denv3rr/blob/main/IMG_4225.gif" />
  </a>
</div>




