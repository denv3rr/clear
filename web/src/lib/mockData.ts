export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

const demoClients = [
  {
    client_id: "atlas",
    name: "Atlas Capital",
    risk_profile: "Balanced",
    accounts_count: 2,
    holdings_count: 18,
    reporting_currency: "USD"
  },
  {
    client_id: "meridian",
    name: "Meridian Wealth",
    risk_profile: "Growth",
    accounts_count: 1,
    holdings_count: 12,
    reporting_currency: "USD"
  }
];

const demoClientDetails: Record<string, any> = {
  atlas: {
    client_id: "atlas",
    name: "Atlas Capital",
    risk_profile: "Balanced",
    accounts_count: 2,
    holdings_count: 18,
    reporting_currency: "USD",
    tax_profile: {
      jurisdiction: "US",
      status: "corporate",
      filing: "quarterly"
    },
    accounts: [
      {
        account_id: "atlas-core",
        account_name: "Atlas Core",
        account_type: "Taxable",
        holdings_count: 12,
        manual_value: 150000,
        tags: ["core", "large-cap"],
        holdings: {
          AAPL: 120,
          MSFT: 80,
          NVDA: 35,
          JPM: 90,
          XOM: 140
        },
        manual_holdings: [{ name: "Private Credit Fund", total_value: 90000 }],
        tax_settings: { withholding: 0.18, harvest_losses: true },
        custodian: "Fidelity",
        ownership_type: "entity"
      },
      {
        account_id: "atlas-alt",
        account_name: "Atlas Alternatives",
        account_type: "Advisory",
        holdings_count: 6,
        manual_value: 240000,
        tags: ["alts"],
        holdings: {
          GLD: 260,
          IEF: 180,
          LQD: 240
        },
        manual_holdings: [{ name: "Real Estate HoldCo", total_value: 140000 }],
        tax_settings: { withholding: 0.12, harvest_losses: false },
        custodian: "Schwab",
        ownership_type: "trust"
      }
    ]
  },
  meridian: {
    client_id: "meridian",
    name: "Meridian Wealth",
    risk_profile: "Growth",
    accounts_count: 1,
    holdings_count: 12,
    reporting_currency: "USD",
    tax_profile: {
      jurisdiction: "US",
      status: "individual",
      filing: "annual"
    },
    accounts: [
      {
        account_id: "meridian-main",
        account_name: "Meridian Main",
        account_type: "Taxable",
        holdings_count: 12,
        manual_value: 60000,
        tags: ["growth"],
        holdings: {
          AMZN: 45,
          GOOGL: 30,
          META: 55,
          TSLA: 25,
          CRWD: 40
        },
        manual_holdings: [{ name: "Early Stage Fund", total_value: 45000 }],
        tax_settings: { withholding: 0.2, harvest_losses: true },
        custodian: "Interactive Brokers",
        ownership_type: "individual"
      }
    ]
  }
};

const demoHistory = [
  { ts: 1700000000, value: 1025000 },
  { ts: 1700600000, value: 1042000 },
  { ts: 1701200000, value: 1031000 },
  { ts: 1701800000, value: 1054000 },
  { ts: 1702400000, value: 1072500 },
  { ts: 1703000000, value: 1066000 },
  { ts: 1703600000, value: 1081500 }
];

const demoReturnSeries = [
  { ts: 1700000000, value: 0.008 },
  { ts: 1700600000, value: -0.004 },
  { ts: 1701200000, value: 0.011 },
  { ts: 1701800000, value: 0.006 },
  { ts: 1702400000, value: -0.002 },
  { ts: 1703000000, value: 0.009 }
];

const demoBenchmarkSeries = [
  { ts: 1700000000, value: 0.006 },
  { ts: 1700600000, value: -0.003 },
  { ts: 1701200000, value: 0.009 },
  { ts: 1701800000, value: 0.004 },
  { ts: 1702400000, value: -0.001 },
  { ts: 1703000000, value: 0.007 }
];

const demoRiskPayload = {
  metrics: {
    mean_annual: 0.14,
    vol_annual: 0.18,
    sharpe: 0.92,
    sortino: 1.14,
    beta: 0.88,
    alpha_annual: 0.04,
    r_squared: 0.76,
    max_drawdown: -0.12,
    var_95: -0.03,
    cvar_95: -0.06
  },
  risk_profile: "Balanced",
  meta: "1Y rolling window",
  returns: demoReturnSeries,
  benchmark_returns: demoBenchmarkSeries,
  distribution: [
    { bin_start: -0.06, bin_end: -0.04, count: 2 },
    { bin_start: -0.04, bin_end: -0.02, count: 4 },
    { bin_start: -0.02, bin_end: 0, count: 8 },
    { bin_start: 0, bin_end: 0.02, count: 14 },
    { bin_start: 0.02, bin_end: 0.04, count: 7 }
  ]
};

const demoRegimePayload = {
  transition_matrix: [
    [0.7, 0.2, 0.1],
    [0.15, 0.7, 0.15],
    [0.1, 0.25, 0.65]
  ],
  state_probs: {
    "Risk Off": 0.28,
    Neutral: 0.47,
    "Risk On": 0.25
  },
  evolution: {
    series: [
      { "Risk Off": 0.25, Neutral: 0.5, "Risk On": 0.25 },
      { "Risk Off": 0.3, Neutral: 0.45, "Risk On": 0.25 },
      { "Risk Off": 0.28, Neutral: 0.47, "Risk On": 0.25 }
    ]
  },
  window: {
    interval: "1M",
    series: [
      { ts: 1700000000, value: 0.42 },
      { ts: 1700600000, value: 0.44 },
      { ts: 1701200000, value: 0.47 },
      { ts: 1701800000, value: 0.46 },
      { ts: 1702400000, value: 0.48 }
    ]
  },
  samples: 90
};

const demoPatterns = {
  entropy: 0.78,
  perm_entropy: 0.64,
  hurst: 0.52,
  change_points: [6, 14, 22],
  motifs: [
    { window: "12-18", distance: 0.12 },
    { window: "20-26", distance: 0.18 }
  ],
  vol_forecast: [0.12, 0.14, 0.13, 0.15, 0.14],
  spectrum: [
    { freq: 0.1, power: 0.22 },
    { freq: 0.2, power: 0.31 },
    { freq: 0.3, power: 0.18 },
    { freq: 0.4, power: 0.12 }
  ],
  wave_surface: {
    x: [1, 2, 3, 4],
    y: [1, 2, 3, 4],
    z: [
      [0.2, 0.28, 0.34, 0.29],
      [0.24, 0.31, 0.38, 0.33],
      [0.21, 0.27, 0.32, 0.3],
      [0.18, 0.24, 0.29, 0.27]
    ],
    axis: {
      x_label: "Sample Index",
      y_label: "Window Row",
      z_label: "Return Value",
      x_unit: "index",
      y_unit: "row",
      z_unit: "return"
    }
  },
  fft_surface: {
    x: [0.1, 0.2, 0.3, 0.4],
    y: [1, 2, 3, 4],
    z: [
      [0.12, 0.18, 0.14, 0.1],
      [0.2, 0.26, 0.21, 0.16],
      [0.17, 0.22, 0.19, 0.14],
      [0.11, 0.16, 0.13, 0.09]
    ],
    axis: {
      x_label: "Frequency",
      y_label: "Window Start",
      z_label: "Log Power",
      x_unit: "cycles/sample",
      y_unit: "index",
      z_unit: "log power"
    }
  }
};

const demoHoldings = [
  {
    ticker: "AAPL",
    name: "Apple Inc.",
    sector: "Technology",
    quantity: 120,
    price: 182.1,
    market_value: 21852,
    change: 240,
    pct: 0.011,
    history: [180, 181, 182, 183, 182]
  },
  {
    ticker: "MSFT",
    name: "Microsoft",
    sector: "Technology",
    quantity: 80,
    price: 412.3,
    market_value: 32984,
    change: -180,
    pct: -0.005,
    history: [406, 409, 410, 412, 412]
  },
  {
    ticker: "JPM",
    name: "JPMorgan",
    sector: "Financials",
    quantity: 90,
    price: 198.9,
    market_value: 17901,
    change: 110,
    pct: 0.006,
    history: [196, 197, 198, 199, 199]
  }
];

const demoDiagnostics = {
  sectors: [
    { sector: "Technology", value: 820000, pct: 0.42 },
    { sector: "Financials", value: 340000, pct: 0.18 },
    { sector: "Energy", value: 220000, pct: 0.11 },
    { sector: "Industrials", value: 180000, pct: 0.09 },
    { sector: "Healthcare", value: 150000, pct: 0.08 }
  ],
  hhi: 0.24,
  gainers: [
    { ticker: "NVDA", pct: 0.024, change: 1200 },
    { ticker: "AAPL", pct: 0.011, change: 240 }
  ],
  losers: [
    { ticker: "LQD", pct: -0.012, change: -180 },
    { ticker: "MSFT", pct: -0.005, change: -180 }
  ]
};

const demoDashboard = (clientId: string, accountId?: string) => ({
  client: demoClients.find((client) => client.client_id === clientId) || demoClients[0],
  account:
    accountId && accountId !== "portfolio"
      ? demoClientDetails[clientId]?.accounts?.find(
          (account: any) => account.account_id === accountId
        )
      : undefined,
  interval: "1M",
  totals: {
    market_value: accountId && accountId !== "portfolio" ? 640000 : 1680000,
    manual_value: accountId && accountId !== "portfolio" ? 120000 : 390000,
    total_value: accountId && accountId !== "portfolio" ? 760000 : 2070000,
    holdings_count: demoHoldings.length,
    manual_count: 2
  },
  holdings: demoHoldings,
  manual_holdings:
    accountId && accountId !== "portfolio"
      ? [{ name: "Infrastructure Co-Invest", total_value: 120000 }]
      : [
          { name: "Private Credit Fund", total_value: 90000 },
          { name: "Real Estate HoldCo", total_value: 140000 }
        ],
  history: demoHistory,
  risk: demoRiskPayload,
  regime: demoRegimePayload,
  diagnostics: demoDiagnostics,
  warnings: ["Rebalance recommended for Technology exposure."]
});

const demoTrackerPoints = [
  {
    id: "flt-001",
    kind: "flight",
    category: "commercial",
    label: "AAL120 JFK-LAX",
    lat: 40.64,
    lon: -73.78,
    altitude_ft: 33000,
    speed_kts: 440,
    speed_heat: 0.62,
    country: "United States",
    operator: "AAL",
    operator_name: "American Airlines",
    flight_number: "AAL120",
    tail_number: "N401AA"
  },
  {
    id: "flt-002",
    kind: "flight",
    category: "private",
    label: "N78GX LAS-DEN",
    lat: 36.08,
    lon: -115.15,
    altitude_ft: 28000,
    speed_kts: 380,
    speed_heat: 0.44,
    country: "United States",
    operator: "Private",
    operator_name: "Private",
    flight_number: "GX78",
    tail_number: "N78GX"
  },
  {
    id: "ship-101",
    kind: "ship",
    category: "cargo",
    label: "Ever Prime",
    lat: 34.05,
    lon: 120.3,
    altitude_ft: null,
    speed_kts: 18,
    speed_heat: 0.3,
    country: "Singapore",
    operator: "Evergreen",
    operator_name: "Evergreen Marine",
    flight_number: null,
    tail_number: null
  }
];

const demoTrackerHistory: Record<string, any> = {
  "flt-001": {
    id: "flt-001",
    point: {
      id: "flt-001",
      label: "AAL120 JFK-LAX",
      category: "commercial",
      kind: "flight",
      icao24: "a1b2c3",
      callsign: "AAL120",
      operator: "AAL",
      operator_name: "American Airlines",
      flight_number: "AAL120",
      tail_number: "N401AA",
      country: "United States",
      altitude_ft: 33000,
      speed_kts: 440
    },
    history: [
      { ts: 1703000000, lat: 40.64, lon: -73.78, speed_kts: 420 },
      { ts: 1703003600, lat: 39.8, lon: -78.1, speed_kts: 430 },
      { ts: 1703007200, lat: 38.4, lon: -83.2, speed_kts: 440 },
      { ts: 1703010800, lat: 37.2, lon: -89.4, speed_kts: 450 },
      { ts: 1703014400, lat: 36.1, lon: -95.8, speed_kts: 440 }
    ],
    summary: {
      points: 5,
      distance_km: 2840.2,
      direction: "W",
      bearing_deg: 273.4,
      avg_speed_kts: 436,
      avg_altitude_ft: 33100,
      duration_sec: 5400,
      route_hint: "JFK-LAX"
    }
  },
  "flt-002": {
    id: "flt-002",
    point: {
      id: "flt-002",
      label: "N78GX LAS-DEN",
      category: "private",
      kind: "flight",
      icao24: "b7c2d4",
      callsign: "GX78",
      operator: "Private",
      operator_name: "Private",
      flight_number: "GX78",
      tail_number: "N78GX",
      country: "United States",
      altitude_ft: 28000,
      speed_kts: 380
    },
    history: [
      { ts: 1703000000, lat: 36.08, lon: -115.15, speed_kts: 350 },
      { ts: 1703003600, lat: 37.1, lon: -111.6, speed_kts: 370 },
      { ts: 1703007200, lat: 38.2, lon: -108.5, speed_kts: 380 }
    ],
    summary: {
      points: 3,
      distance_km: 1200.4,
      direction: "NE",
      bearing_deg: 61.2,
      avg_speed_kts: 367,
      avg_altitude_ft: 28000,
      duration_sec: 3600,
      route_hint: "LAS-DEN"
    }
  },
  "ship-101": {
    id: "ship-101",
    point: {
      id: "ship-101",
      label: "Ever Prime",
      category: "cargo",
      kind: "ship",
      operator: "Evergreen",
      operator_name: "Evergreen Marine",
      country: "Singapore",
      altitude_ft: null,
      speed_kts: 18
    },
    history: [
      { ts: 1703000000, lat: 33.6, lon: 119.8, speed_kts: 16 },
      { ts: 1703010000, lat: 33.8, lon: 120.1, speed_kts: 17 },
      { ts: 1703020000, lat: 34.05, lon: 120.3, speed_kts: 18 }
    ],
    summary: {
      points: 3,
      distance_km: 58.4,
      direction: "NE",
      bearing_deg: 43.1,
      avg_speed_kts: 17,
      avg_altitude_ft: null,
      duration_sec: 7200,
      route_hint: "China Sea"
    }
  }
};

export function getMockTrackerSnapshot(mode: string) {
  const filtered =
    mode === "combined"
      ? demoTrackerPoints
      : demoTrackerPoints.filter((point) =>
          mode === "ships" ? point.kind === "ship" : point.kind === "flight"
        );
  return {
    count: filtered.length,
    warnings: ["OpenSky demo data active."],
    points: filtered
  };
}

const demoIntelMeta = {
  regions: [
    { name: "Global", industries: ["all", "Technology", "Energy", "Finance"] },
    { name: "North America", industries: ["all", "Technology", "Defense"] },
    { name: "EMEA", industries: ["all", "Energy", "Finance"] }
  ],
  industries: ["all", "Technology", "Energy", "Finance", "Defense", "Healthcare"],
  categories: ["Macro", "Policy", "Supply Chain", "Geopolitics"],
  sources: ["Reuters", "Bloomberg", "WSJ", "FT"]
};

const demoIntelSummary = {
  title: "Global Impact Report",
  summary: [
    "Liquidity conditions remain stable with selective tightening in credit.",
    "Energy supply signals continue to drive regional inflation dispersions.",
    "Technology capex outlook steady as demand moderates in Q2."
  ],
  sections: [
    {
      title: "Macro Signals",
      rows: [
        ["Rates", "Sticky in developed markets"],
        ["FX", "USD range-bound with EM volatility"]
      ]
    },
    {
      title: "Sector Notes",
      rows: [
        ["Technology", "Capex holding, AI spend selective"],
        ["Energy", "OPEC discipline remains intact"]
      ]
    },
    {
      title: "Policy",
      rows: [
        ["US", "Fiscal normalization pacing uncertain"],
        ["EU", "Energy subsidies being reduced"]
      ]
    }
  ],
  risk_level: "Moderate",
  risk_score: 6.4,
  confidence: "Medium",
  risk_series: [
    { label: "Mon", value: 5.8 },
    { label: "Tue", value: 6.2 },
    { label: "Wed", value: 6.4 },
    { label: "Thu", value: 6.6 },
    { label: "Fri", value: 6.1 },
    { label: "Sat", value: 5.9 },
    { label: "Sun", value: 6.3 }
  ]
};

const demoWeather = {
  title: "Weather Outlook",
  summary: [
    "North Atlantic storm activity easing.",
    "Gulf production risks remain elevated through Q3."
  ],
  sections: [
    { title: "Transport", rows: [["Shipping", "Minor delays in North Sea"]] },
    { title: "Energy", rows: [["Production", "Gulf downtime risk moderate"]] }
  ],
  risk_level: "Moderate"
};

const demoConflict = {
  title: "Conflict Overview",
  summary: [
    "Supply chain reroutes continue for Black Sea trade lanes.",
    "Defense procurement elevated across NATO corridors."
  ],
  sections: [
    { title: "Shipping", rows: [["Black Sea", "Delays and reroutes ongoing"]] },
    { title: "Defense", rows: [["NATO", "Procurement elevated"]] }
  ],
  risk_level: "Elevated"
};

const demoNewsPayload = {
  items: [
    {
      title: "US Treasuries steady as auction demand improves",
      source: "Reuters",
      url: "https://www.reuters.com",
      published_ts: 1703000000,
      regions: ["Global"],
      industries: ["Finance"],
      tags: ["Rates", "Treasuries"]
    },
    {
      title: "Energy majors extend share buybacks into Q3",
      source: "Bloomberg",
      url: "https://www.bloomberg.com",
      published_ts: 1702950000,
      regions: ["North America"],
      industries: ["Energy"],
      tags: ["Buybacks", "Cash Flow"]
    },
    {
      title: "Defense spending outlook rises for 2025 budgets",
      source: "WSJ",
      url: "https://www.wsj.com",
      published_ts: 1702900000,
      regions: ["EMEA"],
      industries: ["Defense"],
      tags: ["Budgets", "Procurement"]
    },
    {
      title: "Cloud demand growth moderates but remains durable",
      source: "FT",
      url: "https://www.ft.com",
      published_ts: 1702850000,
      regions: ["Global"],
      industries: ["Technology"],
      tags: ["Cloud", "Earnings"]
    }
  ],
  cached: false,
  stale: false,
  skipped: [],
  health: {
    Reuters: { last_ok: 1703000000, fail_count: 0 },
    Bloomberg: { last_ok: 1702950000, fail_count: 0 },
    WSJ: { last_ok: 1702900000, fail_count: 0 },
    FT: { last_ok: 1702850000, fail_count: 0 }
  }
};

const demoSettings = {
  settings: {
    credentials: {
      finnhub_key_set: true,
      smtp_configured: false
    }
  },
  feeds: {
    flights: {
      configured: true,
      url_sources: 0,
      path_sources: 0
    },
    shipping: {
      configured: false
    },
    opensky: {
      credentials_set: true
    }
  },
  system: {
    user: "demo",
    hostname: "clear-demo",
    os: "Linux",
    ip: "127.0.0.1",
    login_time: "2025-01-02 09:12 UTC",
    python_version: "3.11.6",
    cpu_usage: "8%",
    mem_usage: "12%",
    cpu_cores: 8
  },
  system_metrics: {
    cpu_percent: 12,
    mem_percent: 34,
    mem_used_gb: 5.4,
    mem_total_gb: 16,
    disk_percent: 42,
    disk_used_gb: 120,
    disk_total_gb: 256,
    swap_percent: 0
  },
  error: null
};

const demoDiagnosticsPayload = {
  system: {
    hostname: "clear-demo",
    ip: "127.0.0.1",
    os: "Linux",
    cpu_usage: "8%",
    cpu_cores: 8,
    mem_usage: "12%",
    python_version: "3.11.6",
    finnhub_status: true,
    psutil_available: true,
    user: "demo"
  },
  metrics: {
    disk_total_gb: 256,
    disk_used_gb: 120,
    disk_free_gb: 136,
    disk_percent: 42,
    cpu_percent: 12,
    mem_percent: 34,
    mem_used_gb: 5.4,
    mem_total_gb: 16,
    swap_percent: 0
  },
  feeds: {
    flights: { configured: true, url_sources: 0, path_sources: 0 },
    shipping: { configured: false },
    opensky: { credentials_set: true },
    registry: {
      sources: [
        { id: "finnhub", label: "Finnhub", category: "market", status: "degraded" },
        { id: "rss::CNBC Top", label: "CNBC Top", category: "news", status: "ok" },
        { id: "trackers::snapshot", label: "Tracker Snapshot", category: "trackers", status: "ok" },
        { id: "intel::news_cache", label: "Intel News Cache", category: "intel", status: "backoff" }
      ]
    },
    summary: {
      total: 8,
      configured: 6,
      warnings: ["No configured sources for market."],
      health_counts: { ok: 5, degraded: 1, backoff: 1, unknown: 1 }
    }
  },
  trackers: { warning_count: 1, count: demoTrackerPoints.length, warnings: ["OpenSky demo data active."] },
  intel: { news_cache: { status: "fresh", items: demoNewsPayload.items.length, age_hours: 0.5 } },
  clients: { clients: demoClients.length, accounts: 3, holdings: 30, lots: 120 },
  orphans: { holdings: 0, lots: 0 },
  reports: { items: 4, status: "warm" }
};

const demoReport = (format: string, interval: string, detail: string) => {
  if (format === "json") {
    return JSON.stringify(
      {
        interval,
        detail: detail === "true",
        highlights: ["Risk profile stable", "Liquidity coverage adequate"],
        totals: demoDashboard("atlas").totals
      },
      null,
      2
    );
  }
  return `# Client Report\n\nInterval: **${interval}**\n\n## Highlights\n- Risk profile stable\n- Liquidity coverage adequate\n\n## Portfolio Totals\n- Total value: $${demoDashboard("atlas").totals.total_value.toLocaleString()}\n- Holdings: ${demoDashboard("atlas").totals.holdings_count}\n`;
};

export function getMockResponse(path: string) {
  const url = new URL(path, "http://mock.local");
  const { pathname, searchParams } = url;
  const empty = searchParams.get("empty") === "true";
  const parts = pathname.split("/").filter(Boolean);

  if (pathname === "/api/health") {
    return { status: "ok" };
  }
  if (pathname === "/api/tools/diagnostics") {
    return demoDiagnosticsPayload;
  }
  if (pathname === "/api/settings") {
    return demoSettings;
  }
  if (pathname === "/api/intel/meta") {
    return demoIntelMeta;
  }
  if (pathname === "/api/intel/summary") {
    if (empty) {
      return {
        ...demoIntelSummary,
        risk_level: "Unavailable",
        risk_score: null,
        confidence: "Low",
        risk_series: []
      };
    }
    return demoIntelSummary;
  }
  if (pathname === "/api/intel/weather") {
    return demoWeather;
  }
  if (pathname === "/api/intel/conflict") {
    return demoConflict;
  }
  if (pathname === "/api/intel/news") {
    if (empty) {
      return {
        items: [],
        cached: false,
        stale: false,
        skipped: [],
        health: {}
      };
    }
    return demoNewsPayload;
  }
  if (pathname === "/api/clients") {
    if (empty) {
      return { clients: [] };
    }
    return { clients: demoClients };
  }
  if (parts[0] === "api" && parts[1] === "clients") {
    const clientId = parts[2];
    if (parts.length === 3) {
      const detail = demoClientDetails[clientId] || demoClientDetails.atlas;
      return detail;
    }
    if (parts[3] === "dashboard") {
      return demoDashboard(clientId);
    }
    if (parts[3] === "patterns") {
      return demoPatterns;
    }
    if (parts[3] === "accounts") {
      const accountId = parts[4];
      if (parts[5] === "dashboard") {
        return demoDashboard(clientId, accountId);
      }
      if (parts[5] === "patterns") {
        return demoPatterns;
      }
    }
  }
  if (parts[0] === "api" && parts[1] === "reports") {
    const format = searchParams.get("fmt") || "md";
    const interval = searchParams.get("interval") || "1M";
    const detail = searchParams.get("detail") || "false";
    if (parts[2] === "client" && parts[3]) {
      return { content: demoReport(format, interval, detail), format };
    }
  }
  if (parts[0] === "api" && parts[1] === "trackers") {
    if (parts[2] === "snapshot") {
      const mode = searchParams.get("mode") || "combined";
      if (empty) {
        return { count: 0, warnings: ["No tracker data in demo mode."], points: [] };
      }
      return getMockTrackerSnapshot(mode);
    }
    if (parts[2] === "search") {
      const query = (searchParams.get("q") || "").toLowerCase();
      if (!query || query.length < 2) {
        return { count: 0, points: [] };
      }
      const results = demoTrackerPoints.filter((point) => {
        const haystack = [
          point.label,
          point.operator,
          point.operator_name,
          point.flight_number,
          point.tail_number,
          point.id
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(query);
      });
      return {
        count: results.length,
        points: results.map((point) => ({
          id: point.id,
          kind: point.kind,
          label: point.label,
          category: point.category,
          operator: point.operator,
          operator_name: point.operator_name,
          flight_number: point.flight_number
        }))
      };
    }
    if (parts[2] === "detail" && parts[3]) {
      return demoTrackerHistory[parts[3]] || demoTrackerHistory["flt-001"];
    }
  }

  throw new Error(`Mock data missing for ${path}`);
}
