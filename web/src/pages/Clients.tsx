import { useEffect, useMemo, useState } from "react";
import { AreaSparkline, DistributionBars } from "../components/ui/Charts";
import { Card } from "../components/ui/Card";
import { Collapsible } from "../components/ui/Collapsible";
import { KpiCard } from "../components/ui/KpiCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { Surface3D } from "../components/ui/Surface3D";
import { apiGet, useApi } from "../lib/api";

type ClientSummary = {
  client_id: string;
  name: string;
  risk_profile?: string;
  accounts_count: number;
  holdings_count: number;
  reporting_currency?: string;
};

type ClientIndex = {
  clients: ClientSummary[];
};

type AccountDetail = {
  account_id: string;
  account_name: string;
  account_type?: string;
  holdings_count: number;
  manual_value: number;
  tags: string[];
  holdings: Record<string, number>;
  manual_holdings: { name?: string; total_value?: number }[];
  tax_settings: Record<string, string | number | boolean>;
  custodian?: string | null;
  ownership_type?: string | null;
};

type ClientDetail = ClientSummary & {
  tax_profile: Record<string, string | number | boolean>;
  accounts: AccountDetail[];
};

type HistoryPoint = {
  ts: number | null;
  value: number;
};

type RiskPayload = {
  error?: string;
  metrics?: Record<string, number>;
  risk_profile?: string;
  meta?: string;
  returns?: { ts: number | null; value: number }[];
  benchmark_returns?: { ts: number | null; value: number }[];
  distribution?: { bin_start: number; bin_end: number; count: number }[];
};

type RegimePayload = {
  error?: string;
  transition_matrix?: number[][];
  state_probs?: Record<string, number>;
  evolution?: { series?: Record<string, number>[] };
};

type SurfacePayload = {
  z: number[][];
  x?: number[];
  y?: number[];
};

type PatternPayload = {
  error?: string;
  entropy?: number;
  perm_entropy?: number;
  hurst?: number;
  change_points?: number[];
  motifs?: { window: string; distance: number }[];
  vol_forecast?: number[];
  spectrum?: { freq: number; power: number }[];
  wave_surface?: SurfacePayload;
  fft_surface?: SurfacePayload;
};

type DashboardPayload = {
  client: ClientSummary;
  account?: AccountDetail;
  interval: string;
  totals: {
    market_value: number;
    manual_value: number;
    total_value: number;
    holdings_count: number;
    manual_count: number;
  };
  holdings: Array<{
    ticker: string;
    name?: string;
    sector?: string;
    quantity: number;
    price: number;
    market_value: number;
    change: number;
    pct: number;
    history?: number[];
  }>;
  manual_holdings: { name?: string; total_value?: number }[];
  history: HistoryPoint[];
  risk: RiskPayload;
  regime: RegimePayload;
  diagnostics?: {
    sectors: { sector: string; value: number; pct: number }[];
    hhi: number;
    gainers: { ticker: string; pct: number; change: number }[];
    losers: { ticker: string; pct: number; change: number }[];
  };
  warnings: string[];
};

const intervals = ["1W", "1M", "3M", "6M", "1Y"];

const metricLabels: Record<string, string> = {
  mean_annual: "Annual Return",
  vol_annual: "Volatility",
  sharpe: "Sharpe",
  sortino: "Sortino",
  beta: "Beta",
  alpha_annual: "Alpha",
  r_squared: "R-Squared",
  max_drawdown: "Max Drawdown",
  var_95: "VaR 95%",
  cvar_95: "CVaR 95%"
};

export default function Clients() {
  const { data: index } = useApi<ClientIndex>("/api/clients", { interval: 60000 });
  const rows = index?.clients ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [query, setQuery] = useState("");
  const [interval, setInterval] = useState("1M");
  const [selectedAccount, setSelectedAccount] = useState<string>("portfolio");
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [patterns, setPatterns] = useState<PatternPayload | null>(null);

  useEffect(() => {
    if (!selectedId && rows.length) {
      setSelectedId(rows[0].client_id);
    }
  }, [rows, selectedId]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    apiGet<ClientDetail>(`/api/clients/${encodeURIComponent(selectedId)}`, 0)
      .then((payload) => {
        setDetail(payload);
        if (payload.accounts?.length && selectedAccount === "portfolio") {
          setSelectedAccount("portfolio");
        }
      })
      .catch(() => setDetail(null));
  }, [selectedId, selectedAccount]);

  useEffect(() => {
    if (!selectedId) return;
    const path =
      selectedAccount === "portfolio"
        ? `/api/clients/${encodeURIComponent(selectedId)}/dashboard?interval=${encodeURIComponent(interval)}`
        : `/api/clients/${encodeURIComponent(selectedId)}/accounts/${encodeURIComponent(
            selectedAccount
          )}/dashboard?interval=${encodeURIComponent(interval)}`;
    apiGet<DashboardPayload>(path, 0)
      .then(setDashboard)
      .catch(() => setDashboard(null));
  }, [selectedId, selectedAccount, interval]);

  useEffect(() => {
    if (!selectedId) return;
    const path =
      selectedAccount === "portfolio"
        ? `/api/clients/${encodeURIComponent(selectedId)}/patterns?interval=${encodeURIComponent(interval)}`
        : `/api/clients/${encodeURIComponent(selectedId)}/accounts/${encodeURIComponent(
            selectedAccount
          )}/patterns?interval=${encodeURIComponent(interval)}`;
    apiGet<PatternPayload>(path, 0)
      .then(setPatterns)
      .catch(() => setPatterns(null));
  }, [selectedId, selectedAccount, interval]);

  const filtered = useMemo(() => {
    if (!query.trim()) return rows;
    const needle = query.trim().toLowerCase();
    return rows.filter(
      (client) =>
        client.name.toLowerCase().includes(needle) ||
        client.client_id.toLowerCase().includes(needle) ||
        (client.risk_profile || "").toLowerCase().includes(needle)
    );
  }, [rows, query]);

  const accountOptions = useMemo(() => {
    if (!detail?.accounts?.length) return [];
    return detail.accounts.map((account) => ({
      value: account.account_id,
      label: `${account.account_name} (${account.account_id.slice(0, 6)})`
    }));
  }, [detail]);

  const activeTotals = dashboard?.totals;
  const activeHoldings = dashboard?.holdings || [];
  const riskMetrics = dashboard?.risk?.metrics || {};
  const riskMetricRows = Object.keys(metricLabels)
    .filter((key) => key in riskMetrics)
    .map((key) => ({
      key,
      label: metricLabels[key],
      value: Number(riskMetrics[key])
    }));

  return (
    <Card className="rounded-2xl p-6">
      <SectionHeader
        label="CLIENTS"
        title="Portfolio Command Center"
        right={dashboard?.client ? `${dashboard.client.name}` : `${rows.length} clients`}
      />
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="space-y-3 text-sm text-slate-300">
          <label htmlFor="client-search" className="text-xs text-slate-400">
            Search
          </label>
          <input
            id="client-search"
            name="client-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="w-full rounded-xl bg-ink-950/60 border border-slate-800 px-4 py-2 text-sm text-slate-200"
            placeholder="Name, ID, risk profile..."
          />
          {filtered.length === 0 ? (
            <p>No client profiles loaded.</p>
          ) : (
            filtered.map((client) => (
              <button
                key={client.client_id}
                onClick={() => {
                  setSelectedId(client.client_id);
                  setSelectedAccount("portfolio");
                }}
                className={`w-full rounded-xl border px-4 py-3 text-left ${
                  selectedId === client.client_id
                    ? "border-emerald-400/60 text-slate-100"
                    : "border-slate-800/60 text-slate-300"
                }`}
              >
                <p className="text-slate-100 font-medium">{client.name}</p>
                <p className="text-xs text-slate-400">{client.client_id}</p>
                <p className="text-xs text-emerald-300 mt-1">
                  {client.risk_profile || "Risk profile unknown"}
                </p>
              </button>
            ))
          )}
        </div>
        <div className="lg:col-span-3 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-800/60 p-4">
              <p className="text-xs text-slate-400">Interval</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {intervals.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setInterval(opt)}
                    className={`rounded-full border px-3 py-1 text-[11px] ${
                      interval === opt
                        ? "border-emerald-400/70 text-emerald-200"
                        : "border-slate-800/60 text-slate-400"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800/60 p-4">
              <p className="text-xs text-slate-400">Scope</p>
              <select
                id="account-scope"
                name="account-scope"
                value={selectedAccount}
                onChange={(event) => setSelectedAccount(event.target.value)}
                className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
              >
                <option value="portfolio">Client Portfolio</option>
                {accountOptions.map((account) => (
                  <option key={account.value} value={account.value}>
                    {account.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="rounded-xl border border-slate-800/60 p-4 text-xs text-slate-400">
              <p className="text-slate-200">Status</p>
              {dashboard?.warnings?.length ? (
                <div className="mt-2 space-y-1 text-amber-300">
                  {dashboard.warnings.map((warn) => (
                    <p key={warn}>{warn}</p>
                  ))}
                </div>
              ) : (
                <p className="mt-2">Realtime valuations active.</p>
              )}
            </div>
          </div>

          {activeTotals ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <KpiCard
                label="Total Value"
                value={`$${activeTotals.total_value.toFixed(2)}`}
                tone="text-emerald-300"
              />
              <KpiCard
                label="Market Value"
                value={`$${activeTotals.market_value.toFixed(2)}`}
                tone="text-slate-200"
              />
              <KpiCard
                label="Manual Value"
                value={`$${activeTotals.manual_value.toFixed(2)}`}
                tone="text-slate-200"
              />
              <KpiCard
                label="Holdings Count"
                value={`${activeTotals.holdings_count}`}
                tone="text-slate-200"
              />
            </div>
          ) : (
            <div className="rounded-xl border border-slate-800/60 bg-ink-950/50 p-6 text-sm text-slate-400">
              Select a client to load the dashboard.
            </div>
          )}

          <Collapsible title="Portfolio History" meta={dashboard?.interval || "Loading"} open onToggle={() => null}>
            {dashboard?.history?.length ? (
              <AreaSparkline data={dashboard.history} height={220} />
            ) : (
              <p className="text-xs text-slate-500">No history series available.</p>
            )}
          </Collapsible>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Collapsible title="Risk Metrics" meta={dashboard?.risk?.risk_profile || "Loading"} open onToggle={() => null}>
              {dashboard?.risk?.error ? (
                <p className="text-xs text-amber-300">{dashboard.risk.error}</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-slate-300">
                  {riskMetricRows.map((metric) => (
                    <div key={metric.key} className="flex items-center justify-between border-b border-slate-900/60 py-2">
                      <span className="text-slate-400">{metric.label}</span>
                      <span className="text-slate-200">{metric.value.toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              )}
            </Collapsible>
            <Collapsible title="Return Distribution" meta={dashboard?.risk?.meta || "Loading"} open onToggle={() => null}>
              {dashboard?.risk?.distribution?.length ? (
                <DistributionBars data={dashboard.risk.distribution} height={200} />
              ) : (
                <p className="text-xs text-slate-500">No return distribution available.</p>
              )}
            </Collapsible>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Surface3D
              title="Transition Surface"
              z={dashboard?.regime?.transition_matrix || []}
            />
            <div className="glass-panel rounded-2xl p-4">
              <p className="text-xs text-slate-400">Stationary Distribution</p>
              <div className="mt-3 space-y-2 text-xs text-slate-300">
                {dashboard?.regime?.state_probs ? (
                  Object.entries(dashboard.regime.state_probs).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-slate-400">{key}</span>
                      <span className="text-emerald-300">{(value * 100).toFixed(1)}%</span>
                    </div>
                  ))
                ) : (
                  <p className="text-slate-500">No regime surface available.</p>
                )}
              </div>
            </div>
          </div>

          <Collapsible title="Pattern Analysis" meta={patterns?.error ? "Offline" : "Active"} open onToggle={() => null}>
            {patterns?.error ? (
              <p className="text-xs text-amber-300">{patterns.error}</p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 text-xs text-slate-300">
                  <KpiCard label="Entropy" value={patterns?.entropy !== undefined ? patterns.entropy.toFixed(3) : "—"} tone="text-emerald-300" />
                  <KpiCard label="Perm Entropy" value={patterns?.perm_entropy !== undefined ? patterns.perm_entropy.toFixed(3) : "—"} tone="text-slate-200" />
                  <KpiCard label="Hurst" value={patterns?.hurst !== undefined ? patterns.hurst.toFixed(3) : "—"} tone="text-slate-200" />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <Surface3D
                    title="Waveform Surface"
                    z={patterns?.wave_surface?.z || []}
                    x={patterns?.wave_surface?.x}
                    y={patterns?.wave_surface?.y}
                    height={300}
                  />
                  <Surface3D
                    title="FFT Waterfall"
                    z={patterns?.fft_surface?.z || []}
                    x={patterns?.fft_surface?.x}
                    y={patterns?.fft_surface?.y}
                    height={300}
                  />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs text-slate-300">
                  <div className="rounded-xl border border-slate-800/60 p-4">
                    <p className="text-xs text-slate-400 mb-2">Motif Matches</p>
                    {patterns?.motifs?.length ? (
                      patterns.motifs.map((motif) => (
                        <div key={motif.window} className="flex items-center justify-between">
                          <span className="text-slate-400">{motif.window}</span>
                          <span className="text-emerald-300">{motif.distance.toFixed(3)}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-slate-500">No motif matches.</p>
                    )}
                  </div>
                  <div className="rounded-xl border border-slate-800/60 p-4">
                    <p className="text-xs text-slate-400 mb-2">Change Points</p>
                    {patterns?.change_points?.length ? (
                      <p className="text-slate-200">{patterns.change_points.length} detected shifts</p>
                    ) : (
                      <p className="text-slate-500">No change points detected.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </Collapsible>

          <Collapsible title="Holdings Snapshot" meta={`${activeHoldings.length} positions`} open onToggle={() => null}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {activeHoldings.map((holding) => (
                <div key={holding.ticker} className="rounded-xl border border-slate-800/60 p-4">
                  <p className="text-slate-100 font-medium">{holding.ticker}</p>
                  <p className="text-xs text-slate-400">{holding.name || "—"} • {holding.sector || "N/A"}</p>
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-300">
                    <span>Qty {holding.quantity.toFixed(2)}</span>
                    <span>${holding.market_value.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Collapsible>

          <Collapsible title="Diagnostics" meta="Concentration + Movers" open onToggle={() => null}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs text-slate-300">
              <div className="rounded-xl border border-slate-800/60 p-4">
                <p className="text-xs text-slate-400 mb-2">Sector Concentration</p>
                {dashboard?.diagnostics?.sectors?.length ? (
                  <div className="space-y-2">
                    {dashboard.diagnostics.sectors.map((row) => (
                      <div key={row.sector} className="flex items-center justify-between">
                        <span className="text-slate-400">{row.sector}</span>
                        <span className="text-emerald-300">{(row.pct * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                    <div className="pt-2 text-slate-400">HHI {dashboard.diagnostics.hhi.toFixed(3)}</div>
                  </div>
                ) : (
                  <p className="text-slate-500">No sector data available.</p>
                )}
              </div>
              <div className="rounded-xl border border-slate-800/60 p-4">
                <p className="text-xs text-slate-400 mb-2">Top Movers (1D)</p>
                {dashboard?.diagnostics ? (
                  <div className="space-y-2">
                    {(dashboard.diagnostics.gainers || []).map((row) => (
                      <div key={`gain-${row.ticker}`} className="flex items-center justify-between">
                        <span className="text-slate-200">{row.ticker}</span>
                        <span className="text-emerald-300">{(row.pct * 100).toFixed(2)}%</span>
                      </div>
                    ))}
                    {(dashboard.diagnostics.losers || []).map((row) => (
                      <div key={`loss-${row.ticker}`} className="flex items-center justify-between">
                        <span className="text-slate-200">{row.ticker}</span>
                        <span className="text-amber-300">{(row.pct * 100).toFixed(2)}%</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500">No mover data available.</p>
                )}
              </div>
            </div>
          </Collapsible>

          <Collapsible title="Manual Assets" meta={`${dashboard?.manual_holdings?.length || 0} entries`} open onToggle={() => null}>
            {dashboard?.manual_holdings?.length ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {dashboard.manual_holdings.map((holding, idx) => (
                  <div key={`${holding.name || "manual"}-${idx}`} className="rounded-xl border border-slate-800/60 p-4 text-xs text-slate-300">
                    <p className="text-slate-100">{holding.name || "Manual Asset"}</p>
                    <p className="text-slate-400">${(holding.total_value || 0).toFixed(2)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No manual assets recorded.</p>
            )}
          </Collapsible>
        </div>
      </div>
    </Card>
  );
}
