import { Card } from "../components/ui/Card";
import { MeterBar } from "../components/ui/Charts";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { KpiCard } from "../components/ui/KpiCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useApi } from "../lib/api";

type DiagnosticsPayload = {
  system?: {
    hostname?: string;
    ip?: string;
    os?: string;
    cpu_usage?: string;
    cpu_cores?: number | string;
    mem_usage?: string;
    python_version?: string;
    finnhub_status?: boolean;
    psutil_available?: boolean;
    user?: string;
  };
  metrics?: {
    disk_total_gb?: number | null;
    disk_used_gb?: number | null;
    disk_free_gb?: number | null;
    disk_percent?: number | null;
    cpu_percent?: number | null;
    mem_percent?: number | null;
    mem_used_gb?: number | null;
    mem_total_gb?: number | null;
    swap_percent?: number | null;
  };
  feeds?: {
    flights?: {
      configured?: boolean;
      url_sources?: number;
      path_sources?: number;
    };
    shipping?: { configured?: boolean };
    opensky?: { credentials_set?: boolean };
  };
  trackers?: { warning_count?: number; count?: number };
  intel?: { news_cache?: { status?: string; items?: number; age_hours?: number | null } };
  clients?: { clients?: number; accounts?: number; holdings?: number; lots?: number };
  reports?: { items?: number; status?: string };
};

type HealthPayload = {
  status?: string;
};

export default function Tools() {
  const { data, error, refresh } = useApi<DiagnosticsPayload>("/api/tools/diagnostics", {
    interval: 60000
  });
  const { data: health } = useApi<HealthPayload>("/api/health", { interval: 60000 });
  const cpuPercent = data?.metrics?.cpu_percent ?? null;
  const memPercent = data?.metrics?.mem_percent ?? null;
  const diskPercent = data?.metrics?.disk_percent ?? null;
  const swapPercent = data?.metrics?.swap_percent ?? null;
  const authHint = "Check CLEAR_WEB_API_KEY + localStorage clear_api_key.";
  const errorMessages = [
    error
      ? `Diagnostics failed: ${error}${error.includes("401") || error.includes("403") ? ` (${authHint})` : ""}`
      : null
  ].filter(Boolean) as string[];

  return (
    <Card className="rounded-2xl p-5">
      <SectionHeader label="TOOLS" title="Diagnostics" />
      <div className="mt-4">
        <ErrorBanner messages={errorMessages} onRetry={refresh} />
      </div>
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-4 gap-4">
        <KpiCard label="Clients" value={`${data?.clients?.clients ?? 0}`} tone="text-emerald-300" />
        <KpiCard label="Accounts" value={`${data?.clients?.accounts ?? 0}`} tone="text-slate-200" />
        <KpiCard label="Holdings" value={`${data?.clients?.holdings ?? 0}`} tone="text-slate-200" />
        <KpiCard label="Tracker Signals" value={`${data?.trackers?.count ?? 0}`} tone="text-emerald-300" />
      </div>
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6 text-sm text-slate-300">
        <div className="space-y-2">
          <p className="text-slate-100 font-medium">System</p>
          <p>User: {data?.system?.user || "—"}</p>
          <p>Host: {data?.system?.hostname || "—"}</p>
          <p>IP: {data?.system?.ip || "—"}</p>
          <p>OS: {data?.system?.os || "—"}</p>
          <p>CPU: {data?.system?.cpu_usage || "—"}</p>
          <p>Cores: {data?.system?.cpu_cores ?? "—"}</p>
          <p>Memory: {data?.system?.mem_usage || "—"}</p>
          <p>Python: {data?.system?.python_version || "—"}</p>
          <p>Finnhub Key: {data?.system?.finnhub_status ? "Configured" : "Missing"}</p>
          <p>psutil: {data?.system?.psutil_available ? "Available" : "Missing"}</p>
          <p>API Health: {health?.status || "Unknown"}</p>
          <p>
            Flight Feed:{" "}
            {data?.feeds?.flights?.configured
              ? data?.feeds?.flights?.url_sources || data?.feeds?.flights?.path_sources
                ? "Configured"
                : data?.feeds?.opensky?.credentials_set
                ? "OpenSky (auth)"
                : "OpenSky (anon)"
              : "Missing"}{" "}
            ({data?.feeds?.flights?.url_sources ?? 0} URL / {data?.feeds?.flights?.path_sources ?? 0} file)
          </p>
          <p>Shipping Feed: {data?.feeds?.shipping?.configured ? "Configured" : "Missing"}</p>
          <p>OpenSky Creds: {data?.feeds?.opensky?.credentials_set ? "Present" : "Missing"}</p>
          <p>Tracker Warnings: {data?.trackers?.warning_count ?? "—"}</p>
          <p>
            News Cache: {data?.intel?.news_cache?.status || "—"} ({data?.intel?.news_cache?.items ?? 0})
            {data?.intel?.news_cache?.age_hours !== undefined && data?.intel?.news_cache?.age_hours !== null
              ? ` • ${data?.intel?.news_cache?.age_hours}h`
              : ""}
          </p>
          <p>Lots: {data?.clients?.lots ?? "—"}</p>
          <p>Report Cache: {data?.reports?.status || "—"} ({data?.reports?.items ?? 0})</p>
        </div>
        <div className="space-y-2">
          <p className="text-slate-100 font-medium">Utilization</p>
          <p className="text-xs text-slate-400">CPU Load</p>
          <MeterBar value={cpuPercent ?? 0} height={70} max={100} />
          <p className="text-xs text-slate-400 mt-3">Memory Load</p>
          <MeterBar value={memPercent ?? 0} height={70} max={100} />
          <p className="text-xs text-slate-400 mt-3">Disk Usage</p>
          <MeterBar value={diskPercent ?? 0} height={70} max={100} />
          <p className="text-xs text-slate-400 mt-3">Swap Load</p>
          <MeterBar value={swapPercent ?? 0} height={70} max={100} color="#a3e635" />
          <div className="mt-3 text-xs text-slate-400 space-y-1">
            <p>Total: {data?.metrics?.disk_total_gb?.toFixed(2) ?? "—"} GB</p>
            <p>Used: {data?.metrics?.disk_used_gb?.toFixed(2) ?? "—"} GB</p>
            <p>Free: {data?.metrics?.disk_free_gb?.toFixed(2) ?? "—"} GB</p>
          </div>
        </div>
      </div>
    </Card>
  );
}
