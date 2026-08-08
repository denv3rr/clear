import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { Collapsible } from "../components/ui/Collapsible";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { KpiCard } from "../components/ui/KpiCard";
import { Reveal } from "../components/ui/Reveal";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useApi } from "../lib/api";
import { useSceneController } from "../lib/scene";

const OsintWorkspace = lazy(() =>
  import("../components/osint/OsintWorkspace").then((module) => ({
    default: module.OsintWorkspace,
  }))
);

type IntelSummary = {
  risk_level?: string;
  risk_score?: number;
  confidence?: string | null;
  support?: {
    summary?: string;
  };
  risk_series?: { label: string; value: number }[]; 
  news?: {
    sentiment_avg?: number;
    negative_ratio?: number;
    risk_score?: number;
  };
};

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

export default function Dashboard() {
  const [riskOpen, setRiskOpen] = useState(true);
  const [osintOpen, setOsintOpen] = useState(true);
  const [clientsOpen, setClientsOpen] = useState(true);
  const [worldAutoOpened, setWorldAutoOpened] = useState(false);
  const { isOpen: sceneOpen, openScene } = useSceneController();
  const {
    data: intelSummary,
    error: intelError,
    warnings: intelWarnings,
    refresh: refreshIntel
  } = useApi<IntelSummary>("/api/intel/summary?region=Global", {
    interval: 30000
  });
  const {
    data: clientIndex,
    error: clientError,
    warnings: clientWarnings,
    refresh: refreshClients
  } = useApi<ClientIndex>("/api/clients", { interval: 60000 });
  const lastUpdated = useMemo(() => new Date().toLocaleTimeString(), []);
  const clientRows = clientIndex?.clients ?? [];
  const clientSnapshot = useMemo(() => {
    const accountCount = clientRows.reduce((total, client) => total + (client.accounts_count || 0), 0);
    const holdingsCount = clientRows.reduce((total, client) => total + (client.holdings_count || 0), 0);
    const topClients = [...clientRows]
      .sort((left, right) => (right.accounts_count || 0) - (left.accounts_count || 0) || left.name.localeCompare(right.name))
      .slice(0, 4);
    return {
      accountCount,
      clientCount: clientRows.length,
      holdingsCount,
      topClients,
    };
  }, [clientRows]);

  const kpis = useMemo(
    () => [
      {
        label: "Risk Score",
        value: intelSummary?.risk_score !== undefined ? `${intelSummary.risk_score}/10` : "—",
        tone: "text-green-300"
      },
      {
        label: "Risk Level",
        value: intelSummary?.risk_level || "—",
        tone: "text-green-400"
      },
      {
        label: "Data Support",
        value: intelSummary?.support?.summary || "—",
        tone: "text-green-200"
      },
      {
        label: "Accounts",
        value: `${clientSnapshot.accountCount}`,
        tone: "text-slate-100"
      },
      {
        label: "Last Update",
        value: lastUpdated,
        tone: "text-slate-300"
      }
    ],
    [clientSnapshot.accountCount, intelSummary, lastUpdated]
  );

  const riskSeries = useMemo(() => {
    if (intelSummary?.risk_series?.length) {
      return intelSummary.risk_series.map((point) => ({
        day: point.label,
        value: point.value
      }));
    }
    return [];
  }, [intelSummary]);
  const hasRiskSeries = riskSeries.length > 0;

  useEffect(() => {
    if (worldAutoOpened) return;
    setWorldAutoOpened(true);
    openScene("overview");
  }, [openScene, worldAutoOpened]);

  const intelAuthError =
    Boolean(intelError) &&
    (intelError.includes("401") || intelError.includes("403"));
  const errorMessages = [
    intelError && !intelAuthError
      ? `World summary failed: ${intelError}`
      : null,
    clientError ? `Client snapshot failed: ${clientError}` : null,
    ...intelWarnings.map((warning) => `World summary: ${warning}`),
    ...clientWarnings.map((warning) => `Client snapshot: ${warning}`)
  ].filter(Boolean) as string[];

  return (
    <>
      <Reveal>
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="tag text-xs text-slate-300">WORLD</p>
            <h2 className="text-3xl font-semibold">Overview</h2>
          </div>
          <button
            type="button"
            data-testid="overview-open-globe"
            onClick={() => openScene("overview")}
            className="osint-command__globe-button w-fit"
          >
            {sceneOpen ? "World Live" : "Open World"}
          </button>
        </header>
      </Reveal>

      <Reveal delay={0.1}>
        <section className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-5">
          {kpis.map((kpi) => (
            <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} tone={kpi.tone} />
          ))}
        </section>
      </Reveal>

      <Reveal delay={0.15}>
        <div className="mt-6">
          <ErrorBanner messages={errorMessages} onRetry={() => {
            refreshIntel();
            refreshClients();
          }} />
        </div>
      </Reveal>

      <Reveal delay={0.2}>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[0.95fr_1.35fr]">
          <Collapsible
            title="Client And Account Snapshot"
            meta={`${clientSnapshot.clientCount} clients • ${clientSnapshot.accountCount} accounts`}
            open={clientsOpen}
            onToggle={() => setClientsOpen((prev) => !prev)}
          >
            <div className="overview-panel-grid">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Portfolio Scope</p>
                <div className="mt-3 grid grid-cols-3 gap-3">
                  <div className="overview-mini-stat">
                    <span>Clients</span>
                    <strong>{clientSnapshot.clientCount}</strong>
                  </div>
                  <div className="overview-mini-stat">
                    <span>Accounts</span>
                    <strong>{clientSnapshot.accountCount}</strong>
                  </div>
                  <div className="overview-mini-stat">
                    <span>Holdings</span>
                    <strong>{clientSnapshot.holdingsCount}</strong>
                  </div>
                </div>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Top Client Workspaces</p>
                <div className="mt-3 space-y-2">
                  {clientSnapshot.topClients.length ? (
                    clientSnapshot.topClients.map((client) => (
                      <a
                        key={client.client_id}
                        href={`/clients?client=${encodeURIComponent(client.client_id)}`}
                        className="overview-client-row"
                      >
                        <span>{client.name}</span>
                        <small>{client.accounts_count || 0} accounts • {client.risk_profile || "Unprofiled"}</small>
                      </a>
                    ))
                  ) : (
                    <p className="text-xs text-slate-400">No client workspaces available.</p>
                  )}
                </div>
              </div>
            </div>
          </Collapsible>

          <Collapsible
            title="Global Patterns"
            meta={intelSummary?.risk_level || "Live"}
            open={riskOpen}
            onToggle={() => setRiskOpen((prev) => !prev)}
          >
            <div className="h-52">
              {hasRiskSeries ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={riskSeries}>
                    <defs>
                      <linearGradient id="riskGlow" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--green-500)" stopOpacity={0.7} />
                        <stop offset="100%" stopColor="var(--green-500)" stopOpacity={0.11} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="day"
                      stroke="var(--slate-700)"
                      tick={{ fill: "var(--slate-100)", fontSize: 12 }}
                    />
                    <YAxis
                      stroke="var(--slate-700)"
                      tick={{ fill: "var(--slate-100)", fontSize: 12 }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "var(--slate-900)",
                        border: "1px solid var(--slate-700)",
                        color: "var(--slate-100)"
                      }}
                    />
                    <Area type="monotone" dataKey="value" stroke="var(--green-500)" fill="url(#riskGlow)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-slate-400">
                  No risk series available.
                </div>
              )}
            </div>
          </Collapsible>
        </div>
      </Reveal>

      <Reveal delay={0.25}>
        <Collapsible
          title="World Workspace"
          meta="World • Trackers • Signals • News"
          open={osintOpen}
          onToggle={() => setOsintOpen((prev) => !prev)}
          mountWhenOpen
        >
          {intelAuthError ? (
            <p className="mb-4 text-xs text-amber-200">
              Summaries require an API key. Set it in Settings.
            </p>
          ) : null}
          <Suspense
            fallback={
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-5">
                <p className="tag text-xs text-emerald-300">LOADING</p>
                <p className="mt-2 text-sm text-slate-300">Loading world workspace...</p>
              </div>
            }
          >
            <OsintWorkspace embedded />
          </Suspense>
        </Collapsible>
      </Reveal>
    </>
  );
}
