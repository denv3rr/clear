import { useMemo, useState } from "react";
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
    <Card className="rounded-2xl p-6">
      <SectionHeader label="INTEL" title="Global Impact Summary" right={data?.risk_level ?? "Loading"} />
      <div className="mt-4">
        <ErrorBanner messages={errorMessages} onRetry={refresh} />
      </div>
      <div className="mt-6 space-y-4 text-sm text-slate-300">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard label="Risk Level" value={data?.risk_level || "Loading"} tone="text-emerald-300" />
          <KpiCard label="Risk Score" value={data?.risk_score !== undefined ? `${data.risk_score}/10` : "—"} tone="text-slate-200" />
          <KpiCard label="Confidence" value={data?.confidence || "—"} tone="text-slate-200" />
        </div>

        <Collapsible title="Filters" meta={`${region} • ${industry}`} open={filtersOpen} onToggle={() => setFiltersOpen((prev) => !prev)}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div>
              <label htmlFor="intel-region" className="text-xs text-slate-400">
                Region
              </label>
              <select
                id="intel-region"
                name="intel-region"
                value={region}
                onChange={(event) => setRegion(event.target.value)}
                className="mt-1 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
              >
                {regionOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="intel-industry" className="text-xs text-slate-400">
                Industry
              </label>
              <select
                id="intel-industry"
                name="intel-industry"
                value={industry}
                onChange={(event) => setIndustry(event.target.value)}
                className="mt-1 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
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
              <p className="text-xs text-slate-400">Categories</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(meta?.categories || []).map((category) => (
                  <button
                    key={category}
                    type="button"
                    onClick={() => toggleCategory(category)}
                    className={`rounded-full border px-3 py-1 text-[11px] ${
                      categories.includes(category)
                        ? "border-emerald-400/70 text-emerald-200"
                        : "border-slate-800/60 text-slate-400"
                    }`}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-xs text-slate-400">Sources</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(meta?.sources || []).map((source) => (
                <button
                  key={source}
                  type="button"
                  onClick={() => toggleSource(source)}
                  className={`rounded-full border px-3 py-1 text-[11px] ${
                    sources.includes(source)
                      ? "border-emerald-400/70 text-emerald-200"
                      : "border-slate-800/60 text-slate-400"
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
            <div className="rounded-xl border border-slate-800/60 p-4">
              <p className="text-xs text-slate-400 mb-2">Summary</p>
              <div className="space-y-2">
                {(data?.summary || ["No intel payload yet."]).map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {(data?.sections || []).slice(0, 4).map((section) => (
                <div key={section.title} className="rounded-xl border border-slate-800/60 p-4">
                  <p className="text-xs text-slate-400 mb-2">{section.title}</p>
                  {renderRows(section.rows as (string[] | string)[])}
                </div>
              ))}
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
            <div className="rounded-xl border border-slate-800/60 p-4">
              <p className="text-xs text-slate-400 mb-2">Summary</p>
              {(weather?.summary || ["No weather payload yet."]).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
            {(weather?.sections || []).map((section) => (
              <div key={section.title} className="rounded-xl border border-slate-800/60 p-4">
                <p className="text-xs text-slate-400 mb-2">{section.title}</p>
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
            <div className="rounded-xl border border-slate-800/60 p-4">
              <p className="text-xs text-slate-400 mb-2">Summary</p>
              {(conflict?.summary || ["No conflict payload yet."]).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
            {(conflict?.sections || []).map((section) => (
              <div key={section.title} className="rounded-xl border border-slate-800/60 p-4">
                <p className="text-xs text-slate-400 mb-2">{section.title}</p>
                {renderRows(section.rows as (string[] | string)[])}
              </div>
            ))}
          </div>
        </Collapsible>
      </div>
    </Card>
  );
}
