import { FormEvent, useEffect, useMemo, useState } from "react";
import { AreaSparkline, DistributionBars } from "../components/ui/Charts";
import { Card } from "../components/ui/Card";
import { Collapsible } from "../components/ui/Collapsible";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { KpiCard } from "../components/ui/KpiCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { Surface3D } from "../components/ui/Surface3D";
import { apiGet, apiPatch, apiPost, useApi } from "../lib/api";

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
  error_detail?: string;
  transition_matrix?: number[][];
  state_probs?: Record<string, number>;
  evolution?: { series?: Record<string, number>[] };
  window?: { interval?: string; series?: HistoryPoint[] };
};

type SurfacePayload = {
  z: number[][];
  x?: number[];
  y?: number[];
  axis?: {
    x_label?: string;
    y_label?: string;
    z_label?: string;
    x_unit?: string;
    y_unit?: string;
    z_unit?: string;
  };
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

type AccountWriteResponse = {
  client: ClientDetail;
  account: AccountDetail;
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
  const {
    data: index,
    error: indexError,
    loading: indexLoading,
    refresh: refreshIndex
  } = useApi<ClientIndex>("/api/clients", { interval: 60000 });
  const rows = index?.clients ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [interval, setInterval] = useState("1M");
  const [selectedAccount, setSelectedAccount] = useState<string>("portfolio");  
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);    
  const [dashboardError, setDashboardError] = useState<string | null>(null);    
  const [patterns, setPatterns] = useState<PatternPayload | null>(null);        
  const [patternsError, setPatternsError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [profileOpen, setProfileOpen] = useState(true);
  const [riskOpen, setRiskOpen] = useState(true);
  const [distributionOpen, setDistributionOpen] = useState(true);
  const [patternOpen, setPatternOpen] = useState(true);
  const [holdingsOpen, setHoldingsOpen] = useState(true);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(true);
  const [manualOpen, setManualOpen] = useState(true);
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [accountFormOpen, setAccountFormOpen] = useState(false);
  const [accountEditOpen, setAccountEditOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSaving, setFormSaving] = useState(false);
  const [clientForm, setClientForm] = useState({
    name: "",
    risk_profile: "",
    residency_country: "",
    tax_country: "",
    reporting_currency: "USD",
    treaty_country: "",
    tax_id: ""
  });
  const [accountForm, setAccountForm] = useState({
    account_name: "",
    account_type: "Taxable",
    ownership_type: "Individual",
    custodian: "",
    tags: ""
  });
  const [accountEditForm, setAccountEditForm] = useState({
    account_name: "",
    account_type: "",
    ownership_type: "",
    custodian: "",
    tags: ""
  });

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setDetailError(null);
      return;
    }
    apiGet<ClientDetail>(`/api/clients/${encodeURIComponent(selectedId)}`, 0)
      .then((payload) => {
        setDetail(payload);
        setDetailError(null);
        if (payload.accounts?.length && selectedAccount === "portfolio") {
          setSelectedAccount("portfolio");
        }
      })
      .catch((err) => {
        setDetail(null);
        setDetailError(err instanceof Error ? err.message : "Client detail failed.");
      });
  }, [selectedId, selectedAccount]);

  useEffect(() => {
    if (formMode !== "edit" || !detail) return;
    setClientForm({
      name: detail.name || "",
      risk_profile: detail.risk_profile || "",
      residency_country: String(detail.tax_profile?.residency_country || ""),
      tax_country: String(detail.tax_profile?.tax_country || ""),
      reporting_currency: String(detail.tax_profile?.reporting_currency || "USD"),
      treaty_country: String(detail.tax_profile?.treaty_country || ""),
      tax_id: String(detail.tax_profile?.tax_id || "")
    });
  }, [formMode, detail]);

  useEffect(() => {
    if (!accountEditOpen || !detail || selectedAccount === "portfolio") return;
    const account = detail.accounts.find((item) => item.account_id === selectedAccount);
    if (!account) return;
    setAccountEditForm({
      account_name: account.account_name || "",
      account_type: account.account_type || "",
      ownership_type: account.ownership_type || "",
      custodian: account.custodian || "",
      tags: account.tags?.join(", ") || ""
    });
  }, [accountEditOpen, detail, selectedAccount]);

  useEffect(() => {
    if (selectedAccount === "portfolio") {
      setAccountEditOpen(false);
    }
  }, [selectedAccount]);

  useEffect(() => {
    if (!selectedId) return;
    const path =
      selectedAccount === "portfolio"
        ? `/api/clients/${encodeURIComponent(selectedId)}/dashboard?interval=${encodeURIComponent(interval)}`
        : `/api/clients/${encodeURIComponent(selectedId)}/accounts/${encodeURIComponent(
            selectedAccount
          )}/dashboard?interval=${encodeURIComponent(interval)}`;
    apiGet<DashboardPayload>(path, 0)
      .then((payload) => {
        setDashboard(payload);
        setDashboardError(null);
      })
      .catch((err) => {
        setDashboard(null);
        setDashboardError(err instanceof Error ? err.message : "Dashboard failed.");
      });
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
      .then((payload) => {
        setPatterns(payload);
        setPatternsError(null);
      })
      .catch((err) => {
        setPatterns(null);
        setPatternsError(err instanceof Error ? err.message : "Pattern analysis failed.");
      });
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

  const summary = useMemo(() => {
    const accounts = rows.reduce((acc, client) => acc + (client.accounts_count || 0), 0);
    const holdings = rows.reduce((acc, client) => acc + (client.holdings_count || 0), 0);
    return {
      clients: rows.length,
      accounts,
      holdings
    };
  }, [rows]);

  const profileRows = useMemo(() => {
    const entries = Object.entries(detail?.tax_profile || {});
    if (!entries.length) {
      return [["Tax Profile", "No tax profile configured."]];
    }
    return entries.map(([key, value]) => [key, String(value)]);
  }, [detail]);

  const accountRows = useMemo(() => {
    if (!detail?.accounts?.length) return [];
    return detail.accounts.map((account) => ({
      id: account.account_id,
      name: account.account_name,
      type: account.account_type || "N/A",
      custodian: account.custodian || "N/A",
      ownership: account.ownership_type || "N/A",
      tags: account.tags?.length ? account.tags.join(", ") : "None",
      taxKeys: Object.keys(account.tax_settings || {}).length
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
  const authHint = "Check CLEAR_WEB_API_KEY + localStorage clear_api_key.";
  const errorMessages = [
    indexError
      ? `Client index failed: ${indexError}${
          indexError.includes("401") || indexError.includes("403") ? ` (${authHint})` : ""
        }`
      : null,
    detailError ? `Client detail failed: ${detailError}` : null,
    dashboardError ? `Dashboard failed: ${dashboardError}` : null,
    patternsError ? `Patterns failed: ${patternsError}` : null,
    formError ? `Client workflow: ${formError}` : null
  ].filter(Boolean) as string[];

  const resetClientForm = () => {
    setClientForm({
      name: "",
      risk_profile: "",
      residency_country: "",
      tax_country: "",
      reporting_currency: "USD",
      treaty_country: "",
      tax_id: ""
    });
  };

  const resetAccountForm = () => {
    setAccountForm({
      account_name: "",
      account_type: "Taxable",
      ownership_type: "Individual",
      custodian: "",
      tags: ""
    });
  };

  const resetAccountEditForm = () => {
    setAccountEditForm({
      account_name: "",
      account_type: "",
      ownership_type: "",
      custodian: "",
      tags: ""
    });
  };

  const handleCreateClient = async (event: FormEvent) => {
    event.preventDefault();
    setFormSaving(true);
    setFormError(null);
    try {
      const payload = {
        name: clientForm.name.trim(),
        risk_profile: clientForm.risk_profile.trim() || undefined,
        tax_profile: {
          residency_country: clientForm.residency_country.trim(),
          tax_country: clientForm.tax_country.trim(),
          reporting_currency: clientForm.reporting_currency.trim() || "USD",
          treaty_country: clientForm.treaty_country.trim(),
          tax_id: clientForm.tax_id.trim()
        }
      };
      const created = await apiPost<ClientDetail>("/api/clients", payload);
      await refreshIndex();
      setSelectedId(created.client_id);
      setSelectedAccount("portfolio");
      setFormMode(null);
      resetClientForm();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create client.");
    } finally {
      setFormSaving(false);
    }
  };

  const handleUpdateClient = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId) return;
    setFormSaving(true);
    setFormError(null);
    try {
      const payload = {
        name: clientForm.name.trim(),
        risk_profile: clientForm.risk_profile.trim() || undefined,
        tax_profile: {
          residency_country: clientForm.residency_country.trim(),
          tax_country: clientForm.tax_country.trim(),
          reporting_currency: clientForm.reporting_currency.trim() || "USD",
          treaty_country: clientForm.treaty_country.trim(),
          tax_id: clientForm.tax_id.trim()
        }
      };
      const updated = await apiPatch<ClientDetail>(
        `/api/clients/${encodeURIComponent(selectedId)}`,
        payload
      );
      setDetail(updated);
      await refreshIndex();
      setFormMode(null);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to update client.");
    } finally {
      setFormSaving(false);
    }
  };

  const handleAddAccount = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId) return;
    setFormSaving(true);
    setFormError(null);
    try {
      const tags = accountForm.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean);
      const payload = {
        account_name: accountForm.account_name.trim(),
        account_type: accountForm.account_type.trim(),
        ownership_type: accountForm.ownership_type.trim(),
        custodian: accountForm.custodian.trim(),
        tags
      };
      const updated = await apiPost<AccountWriteResponse>(
        `/api/clients/${encodeURIComponent(selectedId)}/accounts`,
        payload
      );
      setDetail(updated.client);
      setSelectedAccount(updated.account.account_id);
      setAccountFormOpen(false);
      resetAccountForm();
      await refreshIndex();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to add account.");
    } finally {
      setFormSaving(false);
    }
  };

  const handleUpdateAccount = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId || selectedAccount === "portfolio") return;
    setFormSaving(true);
    setFormError(null);
    try {
      const tags = accountEditForm.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean);
      const payload = {
        account_name: accountEditForm.account_name.trim(),
        account_type: accountEditForm.account_type.trim(),
        ownership_type: accountEditForm.ownership_type.trim(),
        custodian: accountEditForm.custodian.trim(),
        tags
      };
      const updated = await apiPatch<AccountWriteResponse>(
        `/api/clients/${encodeURIComponent(selectedId)}/accounts/${encodeURIComponent(selectedAccount)}`,
        payload
      );
      setDetail(updated.client);
      setAccountEditOpen(false);
      resetAccountEditForm();
      await refreshIndex();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to update account.");
    } finally {
      setFormSaving(false);
    }
  };

  return (
    <Card className="rounded-2xl p-5">
      <SectionHeader
        label="CLIENTS"
        title="Portfolio Command Center"
        right={
          selectedId
            ? `${detail?.name || "Loading client"}`
            : `${summary.clients} clients`
        }
      />
      <ErrorBanner messages={errorMessages} onRetry={refreshIndex} />
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-6">
        <div className="space-y-3 text-sm text-slate-300">
          <div className="flex items-center justify-between">
            <label htmlFor="client-search" className="text-xs text-slate-400">
              Search
            </label>
            <button
              type="button"
              onClick={() => {
                setFormMode("create");
                setAccountFormOpen(false);
                resetClientForm();
                setFormError(null);
              }}
              className="rounded-full border border-slate-800/70 px-3 py-1 text-[11px] text-slate-300 hover:text-white"
            >
              New Client
            </button>
          </div>
          <input
            id="client-search"
            name="client-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="w-full rounded-xl bg-ink-950/60 border border-slate-800 px-4 py-2 text-sm text-slate-200"
            placeholder="Name, ID, risk profile..."
          />
          {filtered.length === 0 ? (
            <p>{indexLoading ? "Loading client profiles..." : "No client profiles loaded."}</p>
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
        <div className="lg:col-span-3 space-y-5">
          {formMode === "create" ? (
            <div className="rounded-2xl border border-slate-800/60 bg-ink-950/40 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-400">Create Client</p>
                  <p className="text-sm text-slate-100 font-medium">New Client Profile</p>
                </div>
                <button
                  type="button"
                  onClick={() => setFormMode(null)}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
              </div>
              <form className="mt-4 space-y-4" onSubmit={handleCreateClient}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="client-name">
                      Client Name
                    </label>
                    <input
                      id="client-name"
                      value={clientForm.name}
                      onChange={(event) => setClientForm({ ...clientForm, name: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="Atlas Capital"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="risk-profile">
                      Risk Profile
                    </label>
                    <input
                      id="risk-profile"
                      value={clientForm.risk_profile}
                      onChange={(event) => setClientForm({ ...clientForm, risk_profile: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="Balanced"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="reporting-currency">
                      Reporting Currency
                    </label>
                    <input
                      id="reporting-currency"
                      value={clientForm.reporting_currency}
                      onChange={(event) =>
                        setClientForm({ ...clientForm, reporting_currency: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="USD"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="residency-country">
                      Residency Country
                    </label>
                    <input
                      id="residency-country"
                      value={clientForm.residency_country}
                      onChange={(event) =>
                        setClientForm({ ...clientForm, residency_country: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="United States"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="tax-country">
                      Tax Country
                    </label>
                    <input
                      id="tax-country"
                      value={clientForm.tax_country}
                      onChange={(event) => setClientForm({ ...clientForm, tax_country: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="United States"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="treaty-country">
                      Treaty Country
                    </label>
                    <input
                      id="treaty-country"
                      value={clientForm.treaty_country}
                      onChange={(event) =>
                        setClientForm({ ...clientForm, treaty_country: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="Canada"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="tax-id">
                      Tax ID
                    </label>
                    <input
                      id="tax-id"
                      value={clientForm.tax_id}
                      onChange={(event) => setClientForm({ ...clientForm, tax_id: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="Optional"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setFormMode(null)}
                    className="text-xs text-slate-400 hover:text-slate-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={formSaving}
                    className="rounded-full border border-emerald-400/70 px-4 py-1 text-xs text-emerald-200"
                  >
                    {formSaving ? "Saving..." : "Create Client"}
                  </button>
                </div>
              </form>
            </div>
          ) : null}
          {formMode === "edit" && selectedId ? (
            <div className="rounded-2xl border border-slate-800/60 bg-ink-950/40 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-400">Edit Client</p>
                  <p className="text-sm text-slate-100 font-medium">Update Client Profile</p>
                </div>
                <button
                  type="button"
                  onClick={() => setFormMode(null)}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
              </div>
              <form className="mt-4 space-y-4" onSubmit={handleUpdateClient}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-client-name">
                      Client Name
                    </label>
                    <input
                      id="edit-client-name"
                      value={clientForm.name}
                      onChange={(event) => setClientForm({ ...clientForm, name: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-risk-profile">
                      Risk Profile
                    </label>
                    <input
                      id="edit-risk-profile"
                      value={clientForm.risk_profile}
                      onChange={(event) => setClientForm({ ...clientForm, risk_profile: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-reporting-currency">
                      Reporting Currency
                    </label>
                    <input
                      id="edit-reporting-currency"
                      value={clientForm.reporting_currency}
                      onChange={(event) =>
                        setClientForm({ ...clientForm, reporting_currency: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-residency-country">
                      Residency Country
                    </label>
                    <input
                      id="edit-residency-country"
                      value={clientForm.residency_country}
                      onChange={(event) =>
                        setClientForm({ ...clientForm, residency_country: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-tax-country">
                      Tax Country
                    </label>
                    <input
                      id="edit-tax-country"
                      value={clientForm.tax_country}
                      onChange={(event) => setClientForm({ ...clientForm, tax_country: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-treaty-country">
                      Treaty Country
                    </label>
                    <input
                      id="edit-treaty-country"
                      value={clientForm.treaty_country}
                      onChange={(event) =>
                        setClientForm({ ...clientForm, treaty_country: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-tax-id">
                      Tax ID
                    </label>
                    <input
                      id="edit-tax-id"
                      value={clientForm.tax_id}
                      onChange={(event) => setClientForm({ ...clientForm, tax_id: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setFormMode(null)}
                    className="text-xs text-slate-400 hover:text-slate-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={formSaving}
                    className="rounded-full border border-emerald-400/70 px-4 py-1 text-xs text-emerald-200"
                  >
                    {formSaving ? "Saving..." : "Save Changes"}
                  </button>
                </div>
              </form>
            </div>
          ) : null}
          {accountFormOpen && selectedId ? (
            <div className="rounded-2xl border border-slate-800/60 bg-ink-950/40 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-400">Add Account</p>
                  <p className="text-sm text-slate-100 font-medium">New Subaccount</p>
                </div>
                <button
                  type="button"
                  onClick={() => setAccountFormOpen(false)}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
              </div>
              <form className="mt-4 space-y-4" onSubmit={handleAddAccount}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="account-name">
                      Account Name
                    </label>
                    <input
                      id="account-name"
                      value={accountForm.account_name}
                      onChange={(event) =>
                        setAccountForm({ ...accountForm, account_name: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="Primary Brokerage"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="account-type">
                      Account Type
                    </label>
                    <input
                      id="account-type"
                      value={accountForm.account_type}
                      onChange={(event) =>
                        setAccountForm({ ...accountForm, account_type: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="Taxable"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="ownership-type">
                      Ownership Type
                    </label>
                    <input
                      id="ownership-type"
                      value={accountForm.ownership_type}
                      onChange={(event) =>
                        setAccountForm({ ...accountForm, ownership_type: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="Individual"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="custodian">
                      Custodian
                    </label>
                    <input
                      id="custodian"
                      value={accountForm.custodian}
                      onChange={(event) =>
                        setAccountForm({ ...accountForm, custodian: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="Fidelity"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="text-xs text-slate-400" htmlFor="tags">
                      Tags
                    </label>
                    <input
                      id="tags"
                      value={accountForm.tags}
                      onChange={(event) => setAccountForm({ ...accountForm, tags: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      placeholder="Retirement, Core"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setAccountFormOpen(false)}
                    className="text-xs text-slate-400 hover:text-slate-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={formSaving}
                    className="rounded-full border border-emerald-400/70 px-4 py-1 text-xs text-emerald-200"
                  >
                    {formSaving ? "Saving..." : "Add Account"}
                  </button>
                </div>
              </form>
            </div>
          ) : null}
          {accountEditOpen && selectedId && selectedAccount !== "portfolio" ? (
            <div className="rounded-2xl border border-slate-800/60 bg-ink-950/40 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-slate-400">Edit Account</p>
                  <p className="text-sm text-slate-100 font-medium">Update Subaccount</p>
                </div>
                <button
                  type="button"
                  onClick={() => setAccountEditOpen(false)}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
              </div>
              <form className="mt-4 space-y-4" onSubmit={handleUpdateAccount}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-account-name">
                      Account Name
                    </label>
                    <input
                      id="edit-account-name"
                      value={accountEditForm.account_name}
                      onChange={(event) =>
                        setAccountEditForm({ ...accountEditForm, account_name: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-account-type">
                      Account Type
                    </label>
                    <input
                      id="edit-account-type"
                      value={accountEditForm.account_type}
                      onChange={(event) =>
                        setAccountEditForm({ ...accountEditForm, account_type: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-ownership-type">
                      Ownership Type
                    </label>
                    <input
                      id="edit-ownership-type"
                      value={accountEditForm.ownership_type}
                      onChange={(event) =>
                        setAccountEditForm({ ...accountEditForm, ownership_type: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400" htmlFor="edit-custodian">
                      Custodian
                    </label>
                    <input
                      id="edit-custodian"
                      value={accountEditForm.custodian}
                      onChange={(event) =>
                        setAccountEditForm({ ...accountEditForm, custodian: event.target.value })
                      }
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="text-xs text-slate-400" htmlFor="edit-tags">
                      Tags
                    </label>
                    <input
                      id="edit-tags"
                      value={accountEditForm.tags}
                      onChange={(event) => setAccountEditForm({ ...accountEditForm, tags: event.target.value })}
                      className="mt-2 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setAccountEditOpen(false)}
                    className="text-xs text-slate-400 hover:text-slate-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={formSaving}
                    className="rounded-full border border-emerald-400/70 px-4 py-1 text-xs text-emerald-200"
                  >
                    {formSaving ? "Saving..." : "Save Account"}
                  </button>
                </div>
              </form>
            </div>
          ) : null}
          {!selectedId ? (
            <div className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                <KpiCard label="Clients" value={`${summary.clients}`} tone="text-emerald-300" />
                <KpiCard label="Accounts" value={`${summary.accounts}`} tone="text-slate-200" />
                <KpiCard label="Holdings" value={`${summary.holdings}`} tone="text-slate-200" />
              </div>
              <div className="rounded-2xl border border-slate-800/60 bg-ink-950/50 p-6 text-sm text-slate-300">
                <p className="text-slate-100 font-medium">Select a client to load analytics.</p>
                <p className="mt-2 text-slate-400">
                  Choose a profile on the left to open portfolio, risk, and diagnostics views.
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
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
                <label htmlFor="account-scope" className="text-xs text-slate-400">
                  Scope
                </label>
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
                {selectedAccount !== "portfolio" ? (
                  <button
                    type="button"
                    onClick={() => {
                      setAccountEditOpen(true);
                      setAccountFormOpen(false);
                      setFormMode(null);
                      setFormError(null);
                    }}
                    className="mt-3 rounded-full border border-slate-800/70 px-3 py-1 text-[11px] text-slate-300 hover:text-white"
                  >
                    Edit Account
                  </button>
                ) : null}
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
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setFormMode("edit");
                      setAccountFormOpen(false);
                      setFormError(null);
                    }}
                    className="rounded-full border border-slate-800/70 px-3 py-1 text-[11px] text-slate-300 hover:text-white"
                  >
                    Edit Client
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAccountFormOpen(true);
                      setFormMode(null);
                      resetAccountForm();
                      setFormError(null);
                    }}
                    className="rounded-full border border-slate-800/70 px-3 py-1 text-[11px] text-slate-300 hover:text-white"
                  >
                    Add Account
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedId(null)}
                    className="rounded-full border border-slate-800/70 px-3 py-1 text-[11px] text-slate-300 hover:text-white"
                  >
                    Back to overview
                  </button>
                </div>
              </div>
            </div>
          )}

          {selectedId ? (
            activeTotals ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
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
                Loading portfolio snapshot...
              </div>
            )
          ) : null}

          {selectedId ? (
            <>
              <Collapsible
                title="Client Profile"
                meta={detail?.name || "Loading"}
                open={profileOpen}
                onToggle={() => setProfileOpen((prev) => !prev)}
              >
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 text-xs text-slate-300">
              <div className="rounded-xl border border-slate-800/60 p-4">
                <p className="text-xs text-slate-400 mb-2">Tax Profile</p>
                <div className="space-y-2">
                  {profileRows.map(([label, value]) => (
                    <div key={label} className="flex items-center justify-between">
                      <span className="text-slate-400">{label}</span>
                      <span className="text-slate-200">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-xl border border-slate-800/60 p-4">
                <p className="text-xs text-slate-400 mb-2">Accounts</p>
                {accountRows.length ? (
                  <div className="space-y-3">
                    {accountRows.map((account) => (
                      <div key={account.id} className="rounded-lg border border-slate-900/60 p-3">
                        <p className="text-slate-100 font-medium">{account.name}</p>
                        <p className="text-[11px] text-slate-500">{account.id}</p>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-slate-300">
                          <span>Type: {account.type}</span>
                          <span>Custodian: {account.custodian}</span>
                          <span>Ownership: {account.ownership}</span>
                          <span>Tax Keys: {account.taxKeys}</span>
                          <span className="col-span-2">Tags: {account.tags}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500">No accounts available.</p>
                )}
              </div>
            </div>
              </Collapsible>

              <Collapsible
                title="Portfolio History"
                meta={dashboard?.interval || "Loading"}
                open={historyOpen}
                onToggle={() => setHistoryOpen((prev) => !prev)}
              >
            {dashboard?.history?.length ? (
              <AreaSparkline data={dashboard.history} height={220} />
            ) : (
              <p className="text-xs text-slate-500">No history series available.</p>
            )}
              </Collapsible>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <Collapsible
                  title="Risk Metrics"
                  meta={dashboard?.risk?.risk_profile || "Loading"}
                  open={riskOpen}
                  onToggle={() => setRiskOpen((prev) => !prev)}
                >
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
                <Collapsible
                  title="Return Distribution"
                  meta={dashboard?.risk?.meta || "Loading"}
                  open={distributionOpen}
                  onToggle={() => setDistributionOpen((prev) => !prev)}
                >
              {dashboard?.risk?.distribution?.length ? (
                <DistributionBars data={dashboard.risk.distribution} height={200} />
              ) : (
                <p className="text-xs text-slate-500">No return distribution available.</p>
              )}
                </Collapsible>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <Surface3D
                  title="Transition Surface"
                  z={dashboard?.regime?.transition_matrix || []}
                />
                <div className="space-y-4">
                  <div className="glass-panel rounded-2xl p-5">
                    <p className="text-xs text-slate-400">Stationary Distribution</p>
                    <div className="mt-3 space-y-2 text-xs text-slate-300">
                      {dashboard?.regime?.error ? (
                        <p className="text-amber-300">
                          {dashboard.regime.error_detail || dashboard.regime.error}
                        </p>
                      ) : dashboard?.regime?.state_probs ? (
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
                  <div className="glass-panel rounded-2xl p-5">
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-slate-400">Regime Window</p>
                      <p className="text-[11px] text-emerald-300">
                        {dashboard?.regime?.window?.interval || dashboard?.interval || "n/a"}
                      </p>
                    </div>
                    {dashboard?.regime?.window?.series?.length ? (
                      <div className="mt-3">
                        <AreaSparkline
                          data={dashboard.regime.window.series}
                          height={160}
                          color="#48f1a6"
                        />
                        <p className="mt-2 text-[11px] text-slate-500">
                          Samples {dashboard?.regime?.samples ?? 0}
                        </p>
                      </div>
                    ) : dashboard?.regime?.error_detail ? (
                      <p className="mt-3 text-xs text-amber-300">
                        {dashboard.regime.error_detail}
                      </p>
                    ) : (
                      <p className="mt-3 text-xs text-slate-500">
                        No regime window data available.
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <Collapsible
                title="Pattern Analysis"
                meta={patterns?.error ? "Offline" : "Active"}
                open={patternOpen}
                onToggle={() => setPatternOpen((prev) => !prev)}
              >
            {patterns?.error ? (
              <p className="text-xs text-amber-300">{patterns.error}</p>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 text-xs text-slate-300">
                  <KpiCard label="Entropy" value={patterns?.entropy !== undefined ? patterns.entropy.toFixed(3) : "—"} tone="text-emerald-300" />
                  <KpiCard label="Perm Entropy" value={patterns?.perm_entropy !== undefined ? patterns.perm_entropy.toFixed(3) : "—"} tone="text-slate-200" />
                  <KpiCard label="Hurst" value={patterns?.hurst !== undefined ? patterns.hurst.toFixed(3) : "—"} tone="text-slate-200" />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                  <Surface3D
                    title="Waveform Surface"
                    z={patterns?.wave_surface?.z || []}
                    x={patterns?.wave_surface?.x}
                    y={patterns?.wave_surface?.y}
                    axis={patterns?.wave_surface?.axis}
                    height={300}
                  />
                  <Surface3D
                    title="FFT Waterfall"
                    z={patterns?.fft_surface?.z || []}
                    x={patterns?.fft_surface?.x}
                    y={patterns?.fft_surface?.y}
                    axis={patterns?.fft_surface?.axis}
                    height={300}
                  />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 text-xs text-slate-300">
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

              <Collapsible
                title="Holdings Snapshot"
                meta={`${activeHoldings.length} positions`}
                open={holdingsOpen}
                onToggle={() => setHoldingsOpen((prev) => !prev)}
              >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
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

              <Collapsible
                title="Diagnostics"
                meta="Concentration + Movers"
                open={diagnosticsOpen}
                onToggle={() => setDiagnosticsOpen((prev) => !prev)}
              >
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 text-xs text-slate-300">
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

              <Collapsible
                title="Manual Assets"
                meta={`${dashboard?.manual_holdings?.length || 0} entries`}
                open={manualOpen}
                onToggle={() => setManualOpen((prev) => !prev)}
              >
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
            </>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
