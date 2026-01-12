import { useMemo, useState } from "react";
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

type IntelSummary = {
  risk_level?: string;
  risk_score?: number;
  confidence?: string;
  risk_series?: { label: string; value: number }[];
  news?: {
    sentiment_avg?: number;
    negative_ratio?: number;
    risk_score?: number;
  };
};

export default function Dashboard() {
  const [riskOpen, setRiskOpen] = useState(true);
  const [osintOpen, setOsintOpen] = useState(true);
  const {
    data: intelSummary,
    error: intelError,
    warnings: intelWarnings,
    refresh: refreshIntel
  } = useApi<IntelSummary>("/api/intel/summary?region=Global", {
    interval: 30000
  });
  const lastUpdated = useMemo(() => new Date().toLocaleTimeString(), []);

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
        label: "Confidence",
        value: intelSummary?.confidence || "—",
        tone: "text-green-200"
      },
      {
        label: "Last Update",
        value: lastUpdated,
        tone: "text-slate-300"
      }
    ],
    [intelSummary, lastUpdated]
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

  const authHint = "Check CLEAR_WEB_API_KEY + localStorage clear_api_key.";
  const intelAuthError =
    Boolean(intelError) &&
    (intelError.includes("401") || intelError.includes("403"));
  const errorMessages = [
    intelError && !intelAuthError
      ? `Intel summary failed: ${intelError}`
      : null,
    ...intelWarnings.map((warning) => `Intel summary: ${warning}`)
  ].filter(Boolean) as string[];

  return (
    <>
      <Reveal>
        <header className="flex items-center justify-between">
          <div>
            <p className="tag text-xs text-slate-300">GLOBAL OVERVIEW</p>
            <h2 className="text-3xl font-semibold">Overview</h2>
          </div>
        </header>
      </Reveal>

      <Reveal delay={0.1}>
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {kpis.map((kpi) => (
            <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} tone={kpi.tone} />
          ))}
        </section>
      </Reveal>

      <Reveal delay={0.15}>
        <div className="mt-6">
          <ErrorBanner messages={errorMessages} onRetry={() => {
            refreshIntel();
          }} />
        </div>
      </Reveal>

      <Reveal delay={0.2}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div className="lg:col-span-2 space-y-6">
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
  <div className="lg:col-span-1">
    <Collapsible
      title="OSINT"
      meta="Trackers + Intel + News"
      open={osintOpen}
      onToggle={() => setOsintOpen((prev) => !prev)}
    >
      <div className="space-y-3 text-sm text-slate-300">
        <p>
          Live trackers and OSINT intelligence load from the dedicated OSINT hub
          to keep the splash page fast.
        </p>
        {intelAuthError ? (
          <p className="text-xs text-amber-200">
            Intel summary requires an API key. Set it in Settings.
          </p>
        ) : null}
        <a
          href="/osint?tab=trackers"
          className="inline-flex items-center rounded-full border border-slate-700 px-4 py-2 text-xs text-slate-100 hover:border-green-500 hover:text-green-500"
        >
          Open OSINT
        </a>
      </div>
    </Collapsible>
  </div>
</div>
      </Reveal>
    </>
  );
}
