import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { Card } from "../components/ui/Card";
import { Collapsible } from "../components/ui/Collapsible";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { KpiCard } from "../components/ui/KpiCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useApi } from "../lib/api";

type IntelReport = {
  title?: string;
  summary?: string[];
  sections?: { title: string; rows: string[][] }[];
  risk_level?: string;
  risk_score?: number;
  confidence?: string;
  risk_series?: { label: string; value: number }[];
  news?: {
    count?: number;
    risk_score?: number | null;
    sentiment_avg?: number;
    negative_ratio?: number;
    category_counts?: Record<string, number>;
    emotion_counts?: Record<string, number>;
    region_counts?: Record<string, number>;
    subregion_counts?: Record<string, Record<string, number>>;
    timestamp_ratio?: number;
    emotion_series?: { label: string; emotions: Record<string, number> }[];
  };
};

type IntelMeta = {
  regions: { name: string; industries: string[] }[];
  industries: string[];
  categories: string[];
  sources: string[];
};

export default function Intel() {
  const { data: meta, error: metaError } = useApi<IntelMeta>("/api/intel/meta", {
    interval: 600000
  });
  const [region, setRegion] = useState("Global");
  const [industry, setIndustry] = useState("all");
  const [categories, setCategories] = useState<string[]>([]);
  const [sources, setSources] = useState<string[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(true);
  const [fusionOpen, setFusionOpen] = useState(true);
  const [weatherOpen, setWeatherOpen] = useState(true);
  const [conflictOpen, setConflictOpen] = useState(true);

  const categoriesParam = categories.length ? `&categories=${encodeURIComponent(categories.join(","))}` : "";
  const sourcesParam = sources.length ? `&sources=${encodeURIComponent(sources.join(","))}` : "";
  const intelQuery = useMemo(
    () =>
      `/api/intel/summary?region=${encodeURIComponent(region)}&industry=${encodeURIComponent(industry)}${categoriesParam}${sourcesParam}`,
    [region, industry, categoriesParam, sourcesParam]
  );
  const weatherQuery = useMemo(
    () => `/api/intel/weather?region=${encodeURIComponent(region)}&industry=${encodeURIComponent(industry)}`,
    [region, industry]
  );
  const conflictQuery = useMemo(
    () =>
      `/api/intel/conflict?region=${encodeURIComponent(region)}&industry=${encodeURIComponent(industry)}${categoriesParam}${sourcesParam}`,
    [region, industry, categoriesParam, sourcesParam]
  );
  const { data, error: summaryError, refresh } = useApi<IntelReport>(intelQuery, {
    interval: 60000
  });
  const { data: weather, error: weatherError } = useApi<IntelReport>(weatherQuery, {
    interval: 120000
  });
  const { data: conflict, error: conflictError } = useApi<IntelReport>(conflictQuery, {
    interval: 120000
  });
  const authHint = "Check CLEAR_WEB_API_KEY + localStorage clear_api_key.";
  const errorMessages = [
    metaError ? `Intel metadata failed: ${metaError}` : null,
    summaryError
      ? `Summary failed: ${summaryError}${summaryError.includes("401") || summaryError.includes("403") ? ` (${authHint})` : ""}`
      : null,
    weatherError ? `Weather failed: ${weatherError}` : null,
    conflictError ? `Conflict failed: ${conflictError}` : null
  ].filter(Boolean) as string[];

  const regionOptions = meta?.regions?.map((entry) => entry.name) || ["Global"];
  const industryOptions = meta?.industries || ["all"];

  const toggleCategory = (value: string) => {
    setCategories((prev) => (prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]));
  };
  const toggleSource = (value: string) => {
    setSources((prev) => (prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]));
  };

  const categoryMix = useMemo(() => {
    const entries = Object.entries(data?.news?.category_counts || {});
    return entries.sort((a, b) => b[1] - a[1]);
  }, [data?.news?.category_counts]);

  const emotionMix = useMemo(() => {
    const entries = Object.entries(data?.news?.emotion_counts || {});
    return entries.sort((a, b) => b[1] - a[1]);
  }, [data?.news?.emotion_counts]);

  const regionMix = useMemo(() => {
    const entries = Object.entries(data?.news?.region_counts || {});
    return entries.sort((a, b) => b[1] - a[1]);
  }, [data?.news?.region_counts]);

  const subregionMix = useMemo(() => {
    const entries = Object.entries(data?.news?.subregion_counts || {});
    const flat: Array<[string, number]> = [];
    entries.forEach(([regionName, industries]) => {
      Object.entries(industries || {}).forEach(([industryName, count]) => {
        flat.push([`${regionName} • ${industryName}`, count]);
      });
    });
    return flat.sort((a, b) => b[1] - a[1]);
  }, [data?.news?.subregion_counts]);

  const topEmotions = useMemo(() => emotionMix.slice(0, 3).map(([name]) => name), [emotionMix]);

  const emotionSeries = useMemo(() => {
    const series = data?.news?.emotion_series || [];
    if (!series.length || !topEmotions.length) {
      return [];
    }
    return series.map((entry) => {
      const row: Record<string, number | string> = { label: entry.label };
      topEmotions.forEach((emotion) => {
        row[emotion] = entry.emotions?.[emotion] || 0;
      });
      return row;
    });
  }, [data?.news?.emotion_series, topEmotions]);

  const timestampCoverage = data?.news?.timestamp_ratio ?? 0;
  const showTrendData = timestampCoverage >= 0.2 && (data?.risk_series || []).length > 0;

  const renderRows = (rows?: (string[] | string)[]) => {
    if (!rows || rows.length === 0) {
      return <p className="text-xs text-slate-500">No detail rows available.</p>;
    }
    return (
      <div className="space-y-2 text-xs text-slate-300">
        {rows.map((row, idx) => {
          if (Array.isArray(row)) {
            const [label, value] = row;
            return (
              <div key={`${label}-${idx}`} className="flex items-start justify-between gap-4">
                <span className="text-slate-400">{label}</span>
                <span className="text-right text-slate-200">{value || "-"}</span>
              </div>
            );
          }
          return (
            <p key={`${row}-${idx}`} className="text-slate-300">
              {row}
            </p>
          );
        })}
      </div>
    );
  };

  return (
    <Card className="rounded-2xl p-5">
      <SectionHeader label="INTEL" title="Global Impact Summary" right={data?.risk_level ?? "Loading"} />
      <div className="mt-4">
        <ErrorBanner messages={errorMessages} onRetry={refresh} />
      </div>
      <div className="mt-6 space-y-4 text-sm text-slate-300">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard label="Risk Level" value={data?.risk_level || "Loading"} tone="text-green-300" />
          <KpiCard label="Risk Score" value={data?.risk_score !== undefined ? `${data.risk_score}/10` : "—"} tone="text-slate-100" />
          <KpiCard label="Confidence" value={data?.confidence || "—"} tone="text-slate-100" />
        </div>

        <Collapsible title="Filters" meta={`${region} • ${industry}`} open={filtersOpen} onToggle={() => setFiltersOpen((prev) => !prev)}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div>
              <label htmlFor="intel-region" className="text-xs text-slate-300">
                Region
              </label>
              <select
                id="intel-region"
                name="intel-region"
                value={region}
                onChange={(event) => setRegion(event.target.value)}
                className="mt-1 w-full rounded-xl bg-slate-950/60 border border-slate-700 px-3 py-2 text-sm text-slate-100"
              >
                {regionOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="intel-industry" className="text-xs text-slate-300">
                Industry
              </label>
              <select
                id="intel-industry"
                name="intel-industry"
                value={industry}
                onChange={(event) => setIndustry(event.target.value)}
                className="mt-1 w-full rounded-xl bg-slate-950/60 border border-slate-700 px-3 py-2 text-sm text-slate-100"
              >
                <option value="all">All</option>
                {industryOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <p className="text-xs text-slate-300">Categories</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(meta?.categories || []).map((category) => (
                  <button
                    key={category}
                    type="button"
                    onClick={() => toggleCategory(category)}
                    className={`rounded-full border px-3 py-1 text-[11px] ${
                      categories.includes(category)
                        ? "border-green-400/70 text-green-200"
                        : "border-slate-700 text-slate-300"
                    }`}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-xs text-slate-300">Sources</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(meta?.sources || []).map((source) => (
                <button
                  key={source}
                  type="button"
                  onClick={() => toggleSource(source)}
                  className={`rounded-full border px-3 py-1 text-[11px] ${
                    sources.includes(source)
                      ? "border-green-400/70 text-green-200"
                      : "border-slate-700 text-slate-300"
                  }`}
                >
                  {source}
                </button>
              ))}
            </div>
          </div>
        </Collapsible>

        <Collapsible
          title="Combined Overview"
          meta={data?.title || "Global Impact Report"}
          open={fusionOpen}
          onToggle={() => setFusionOpen((prev) => !prev)}
        >
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-700 p-4">
              <p className="text-xs text-slate-300 mb-2">Summary</p>
              <div className="space-y-2">
                {(data?.summary || ["No intel payload yet."]).map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="rounded-xl border border-slate-700 p-4">
                <p className="text-xs text-slate-300 mb-2">Global Risk Trend</p>
                {showTrendData ? (
                  <div className="h-40 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={data.risk_series}>
                        <defs>
                          <linearGradient id="riskFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--green-500)" stopOpacity={0.6} />
                            <stop offset="95%" stopColor="var(--slate-900)" stopOpacity={0.1} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="var(--slate-700)" strokeDasharray="3 3" />
                        <XAxis dataKey="label" tick={{ fill: "var(--slate-300)", fontSize: 10 }} />
                        <YAxis tick={{ fill: "var(--slate-300)", fontSize: 10 }} domain={[0, 10]} />
                        <Tooltip contentStyle={{ background: "var(--slate-900)", borderRadius: 8, borderColor: "var(--slate-700)" }} />
                        <Area type="monotone" dataKey="value" stroke="var(--green-500)" fill="url(#riskFill)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">
                    Time trend unavailable (missing timestamps).
                  </p>
                )}
              </div>
              <div className="rounded-xl border border-slate-700 p-4">
                <p className="text-xs text-slate-300 mb-2">Emotion Trend</p>
                {showTrendData && emotionSeries.length > 0 ? (
                  <div className="h-40 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={emotionSeries}>
                        <CartesianGrid stroke="var(--slate-700)" strokeDasharray="3 3" />
                        <XAxis dataKey="label" tick={{ fill: "var(--slate-300)", fontSize: 10 }} />
                        <YAxis tick={{ fill: "var(--slate-300)", fontSize: 10 }} />
                        <Tooltip contentStyle={{ background: "var(--slate-900)", borderRadius: 8, borderColor: "var(--slate-700)" }} />
                        {topEmotions.map((emotion, index) => (
                          <Bar
                            key={emotion}
                            dataKey={emotion}
                            stackId="emotion"
                            fill={index === 0 ? "var(--green-400)" : index === 1 ? "var(--green-300)" : "var(--green-200)"}
                          />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">
                    Time trend unavailable (missing timestamps).
                  </p>
                )}
              </div>
              <div className="rounded-xl border border-slate-700 p-4">
                <p className="text-xs text-slate-300 mb-2">Category Mix</p>
                {categoryMix.length > 0 ? (
                  <div className="space-y-2 text-xs text-slate-100">
                    {categoryMix.slice(0, 6).map(([category, count]) => (
                      <div key={category} className="flex items-center justify-between">
                        <span className="text-slate-300">{category}</span>
                        <span className="text-slate-100">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">No category mix available yet.</p>
                )}
                {emotionMix.length > 0 ? (
                  <div className="mt-4 space-y-2 text-xs text-slate-100">
                    <p className="text-xs text-slate-300">Emotion Mix</p>
                    {emotionMix.slice(0, 6).map(([emotion, count]) => (
                      <div key={emotion} className="flex items-center justify-between">
                        <span className="text-slate-300">{emotion}</span>
                        <span className="text-slate-100">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="rounded-xl border border-slate-700 p-4">
                <p className="text-xs text-slate-300 mb-2">Regional Coverage</p>
                {regionMix.length > 0 ? (
                  <div className="space-y-2 text-xs text-slate-100">
                    {regionMix.slice(0, 6).map(([regionName, count]) => (
                      <div key={regionName} className="flex items-center justify-between">
                        <span className="text-slate-300">{regionName}</span>
                        <span className="text-slate-100">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">No regional coverage data yet.</p>
                )}
              </div>
              <div className="rounded-xl border border-slate-700 p-4">
                <p className="text-xs text-slate-300 mb-2">Subregional Coverage</p>
                {subregionMix.length > 0 ? (
                  <div className="space-y-2 text-xs text-slate-100">
                    {subregionMix.slice(0, 6).map(([label, count]) => (
                      <div key={label} className="flex items-center justify-between">
                        <span className="text-slate-300">{label}</span>
                        <span className="text-slate-100">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">No subregional coverage data yet.</p>
                )}
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {(data?.sections || []).slice(0, 4).map((section) => (
                <div key={section.title} className="rounded-xl border border-slate-700 p-4">
                  <p className="text-xs text-slate-300 mb-2">{section.title}</p>
                  {renderRows(section.rows as (string[] | string)[])}
                </div>
              ))}
            </div>
            <div className="rounded-xl border border-slate-700 p-4">
              <p className="text-xs text-slate-300 mb-2">News Metrics</p>
              {renderRows([
                ["Articles", String(data?.news?.count ?? 0)],
                ["Sentiment avg", String(data?.news?.sentiment_avg ?? 0)],
                ["Negative ratio", String(data?.news?.negative_ratio ?? 0)],
                [
                  "News risk score",
                  data?.news?.risk_score !== undefined && data?.news?.risk_score !== null
                    ? `${data?.news?.risk_score}/10`
                    : "Unavailable"
                ]
              ])}
            </div>
          </div>
        </Collapsible>

        <Collapsible
          title="Weather Data"
          meta={weather?.risk_level || "Loading"}
          open={weatherOpen}
          onToggle={() => setWeatherOpen((prev) => !prev)}
        >
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-xl border border-slate-700 p-4">
              <p className="text-xs text-slate-300 mb-2">Summary</p>
              {(weather?.summary || ["No weather payload yet."]).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
            {(weather?.sections || []).map((section) => (
              <div key={section.title} className="rounded-xl border border-slate-700 p-4">
                <p className="text-xs text-slate-300 mb-2">{section.title}</p>
                {renderRows(section.rows as (string[] | string)[])}
              </div>
            ))}
          </div>
        </Collapsible>

        <Collapsible
          title="Conflict Data"
          meta={conflict?.risk_level || "Loading"}
          open={conflictOpen}
          onToggle={() => setConflictOpen((prev) => !prev)}
        >
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-xl border border-slate-700 p-4">
              <p className="text-xs text-slate-300 mb-2">Summary</p>
              {(conflict?.summary || ["No conflict payload yet."]).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
            {(conflict?.sections || []).map((section) => (
              <div key={section.title} className="rounded-xl border border-slate-700 p-4">
                <p className="text-xs text-slate-300 mb-2">{section.title}</p>
                {renderRows(section.rows as (string[] | string)[])}
              </div>
            ))}
          </div>
        </Collapsible>
      </div>
    </Card>
  );
}
