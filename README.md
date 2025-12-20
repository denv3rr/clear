<div align="center">

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Repo Size](https://img.shields.io/github/repo-size/denv3rr/clear)
![GitHub Created At](https://img.shields.io/github/created-at/denv3rr/clear)
![Last Commit](https://img.shields.io/github/last-commit/denv3rr/clear)
![Issues](https://img.shields.io/github/issues/denv3rr/clear)
![License](https://img.shields.io/github/license/denv3rr/clear)
![Top Language](https://img.shields.io/github/languages/top/denv3rr/clear)
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

---

<div align="center">

[Overview](#overview) •
[Features](#features) •
[Screenshots](#screenshots) •
[Quick Start](#quick-start) •
[Configuration](#configuration) •
[Modules](#modules) •
[Data Sources](#data-sources) •
[Financial Methods](#financial-methods) •
[Roadmap](#roadmap) •
[Disclaimer](#disclaimer)

</div>

---

## Overview

A terminal-first portfolio management and analytics suite.
<!--
Fast, readable client dashboards, regime modeling, and market context.
Designed for iterative expansion across client workflows, risk analytics, and international tax settings when needed.
-->

## Features

- Client and account management with lot-aware holdings
- Regime analysis (Markov) with transition matrices and surfaces
- Portfolio and account risk metrics (CAPM + derived analytics)
- Market data dashboard with multi-interval views
- Modular settings and tax profile scaffolding

## Screenshots

<!--
<img src="assets/welcome_screen_1.png" alt="Welcome Screen" width="70%" />
-->

## Quick Start

```pwsh
git clone git@github.com:denv3rr/clear.git --depth 1
cd clear
python run.py
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

Do not commit `.env` files.

## Modules

- **Client Manager**: client profiles, accounts, holdings, lots, and tax settings
- **Market Feed**: macro dashboard, tickers, and interval switching
- **Financial Tools**: analytics, CAPM metrics, regime modeling
- **Settings**: API config, device info, preferences

## Data Sources

- **Finnhub**: symbols and quotes (optional)
- **Yahoo Finance**: historical data and macro snapshots

## Financial Methods

<details>
<summary><strong>Formulas and references</strong></summary>

All formulas are shown in plain text blocks to ensure consistent rendering.

### Returns and volatility

```
Simple return: r_t = (P_t / P_{t-1}) - 1
Annualized mean return: μ_annual = mean(r) * A
Annualized volatility: σ_annual = std(r) * sqrt(A)
```

Source: https://www.sec.gov/Archives/edgar/data/0000895421/000089542108000533/texassteel8kex991.htm

### Beta, alpha, and R-squared

```
Beta: β = Cov(r_p, r_m) / Var(r_m)
CAPM expected return: E[r_p] = r_f + β * (E[r_m] - r_f)
Alpha: α = r_p - (r_f + β * (r_m - r_f))
R-squared: R^2 = Corr(r_p, r_m)^2
```

Source: https://www.sec.gov/Archives/edgar/data/0000895421/000089542108000533/texassteel8kex991.htm

### Sharpe ratio

```
Sharpe: S = (mean(r_p) - r_f) / std(r_p)
```

Source: https://www.investor.gov/introduction-investing/investing-basics/terms-and-definitions/sharpe-ratio

### Sortino ratio

```
Sortino: S = (mean(r_p) - r_f) / std(r_p | r_p < r_f)
```

Source: https://www.cfainstitute.org/en/programs/cfa/curriculum

### Treynor ratio

```
Treynor: T = (mean(r_p) - r_f) / β
```

Source: https://www.cfainstitute.org/en/programs/cfa/curriculum

### Tracking error and information ratio

```
Tracking Error: TE = std(r_p - r_b)
Information Ratio: IR = mean(r_p - r_b) / TE
```

Source: https://www.cfainstitute.org/en/programs/cfa/curriculum

### M² (Modigliani-Modigliani)

```
M² = r_f + ((mean(r_p) - r_f) / std(r_p)) * std(r_m)
```

Source: https://www.cfainstitute.org/en/programs/cfa/curriculum

### Max drawdown

```
Drawdown_t = (V_t / peak(V)) - 1
Max Drawdown = min(Drawdown_t)
```

Source: https://www.cfainstitute.org/en/programs/cfa/curriculum

### Value at Risk (historical)

```
VaR_q = quantile(r, 1 - q)
CVaR_q = mean(r | r <= VaR_q)
```

Source: https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/understanding-value-risk

</details>

## Roadmap

- International tax rule sets and jurisdiction presets
- Portfolio timeline audit (full lot history views)
- Global market ticker enhancements and sidebar UX
- Additional analytics models (drawdown, factor exposure)

## Disclaimer

All content is provided **'as is'** without warranty; users should consult with a qualified professional before making any investment or financial decisions.

This project is for **informational use** and does not provide financial, legal, or tax advice.

No information presented should be construed as an offer to buy or sell securities. **The author assumes no liability for financial losses or decisions made based on the contents of this project**.
