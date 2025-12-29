import { useState } from "react";
import { Card } from "../components/ui/Card";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { MeterBar } from "../components/ui/Charts";
import { SectionHeader } from "../components/ui/SectionHeader";
import { clearApiKey, getApiKey, setApiKey, useApi } from "../lib/api";

type SettingsPayload = {
  settings: {
    credentials?: {
      finnhub_key_set?: boolean;
      smtp_configured?: boolean;
    };
  };
  feeds?: {
    flights?: {
      url_sources?: number;
      path_sources?: number;
      configured?: boolean;
    };
    shipping?: {
      configured?: boolean;
    };
    opensky?: {
      credentials_set?: boolean;
    };
  };
  system?: {
    user?: string;
    hostname?: string;
    os?: string;
    ip?: string;
    login_time?: string;
    python_version?: string;
    cpu_usage?: string;
    mem_usage?: string;
    cpu_cores?: number | string;
  };
  system_metrics?: {
    cpu_percent?: number | null;
    mem_percent?: number | null;
    mem_used_gb?: number | null;
    mem_total_gb?: number | null;
    disk_percent?: number | null;
    disk_used_gb?: number | null;
    disk_total_gb?: number | null;
    swap_percent?: number | null;
  };
  error?: string | null;
};

export default function Settings() {
  const { data, error, refresh } = useApi<SettingsPayload>("/api/settings", { interval: 60000 });
  const [apiKeyValue, setApiKeyValue] = useState(getApiKey() || "");
  const [apiKeySaved, setApiKeySaved] = useState(Boolean(getApiKey()));
  const [apiKeyMessage, setApiKeyMessage] = useState<string | null>(null);

  const metrics = data?.system_metrics;
  const authHint = "Check CLEAR_WEB_API_KEY + localStorage clear_api_key.";
  const errorMessages = [
    error
      ? `Settings failed: ${error}${error.includes("401") || error.includes("403") ? ` (${authHint})` : ""}`
      : null
  ].filter(Boolean) as string[];

  return (
    <Card className="rounded-2xl p-5">
      <SectionHeader label="SETTINGS" title="System Settings Snapshot" />
      <div className="mt-4">
        <ErrorBanner messages={errorMessages} onRetry={refresh} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="text-sm text-slate-300 space-y-3">
          {data?.error && <p className="text-amber-300">{data.error}</p>}
          <div className="flex items-center justify-between border-b border-slate-900/60 py-2">
            <p>Finnhub Key</p>
            <p>{data?.settings?.credentials?.finnhub_key_set ? "Configured" : "Missing"}</p>
          </div>
          <div className="flex items-center justify-between border-b border-slate-900/60 py-2">
            <p>SMTP</p>
            <p>{data?.settings?.credentials?.smtp_configured ? "Configured" : "Missing"}</p>
          </div>
          <div className="mt-4 rounded-xl border border-slate-800/60 p-4">
            <p className="text-xs text-slate-400 mb-2">Tracker Feeds</p>
            <div className="flex items-center justify-between border-b border-slate-900/60 py-2">
              <p>Flight Feeds</p>
              <p>
                {data?.feeds?.flights?.configured
                  ? `${data?.feeds?.flights?.url_sources ?? 0} URLs / ${data?.feeds?.flights?.path_sources ?? 0} files`
                  : "Not configured"}
              </p>
            </div>
            <div className="flex items-center justify-between border-b border-slate-900/60 py-2">
              <p>Shipping Feed</p>
              <p>{data?.feeds?.shipping?.configured ? "Configured" : "Missing"}</p>
            </div>
            <div className="flex items-center justify-between py-2">
              <p>OpenSky Credentials</p>
              <p>{data?.feeds?.opensky?.credentials_set ? "Configured" : "Missing"}</p>
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800/60 p-4 text-sm text-slate-300">
            <p className="text-xs text-slate-400 mb-2">System Overview</p>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="space-y-1">
                <p className="text-slate-400">User</p>
                <p>{data?.system?.user ?? "unknown"}</p>
              </div>
              <div className="space-y-1">
                <p className="text-slate-400">Host</p>
                <p>{data?.system?.hostname ?? "unknown"}</p>
              </div>
              <div className="space-y-1">
                <p className="text-slate-400">OS</p>
                <p>{data?.system?.os ?? "unknown"}</p>
              </div>
              <div className="space-y-1">
                <p className="text-slate-400">Python</p>
                <p>{data?.system?.python_version ?? "unknown"}</p>
              </div>
              <div className="space-y-1">
                <p className="text-slate-400">IP</p>
                <p>{data?.system?.ip ?? "unknown"}</p>
              </div>
              <div className="space-y-1">
                <p className="text-slate-400">Session</p>
                <p>{data?.system?.login_time ?? "unknown"}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-800/60 p-4 text-sm text-slate-300">
            <p className="text-xs text-slate-400 mb-2">API Access Key</p>
            <p className="text-xs text-slate-500">
              Required when `CLEAR_WEB_API_KEY` is set on the API server.
            </p>
            <div className="mt-3 space-y-2">
              <input
                id="clear-api-key"
                name="clear-api-key"
                value={apiKeyValue}
                onChange={(event) => setApiKeyValue(event.target.value)}
                className="w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                placeholder="Paste API key"
              />
              <div className="flex flex-wrap gap-2 items-center">
                <button
                  type="button"
                  onClick={() => {
                    const next = apiKeyValue.trim();
                    if (!next) {
                      setApiKeyMessage("Enter a key before saving.");
                      setApiKeySaved(false);
                      return;
                    }
                    setApiKey(next);
                    setApiKeySaved(true);
                    setApiKeyMessage("Key saved locally.");
                  }}
                  className="rounded-full border border-emerald-400/60 px-3 py-1 text-[11px] text-emerald-200"
                >
                  Save Key
                </button>
                <button
                  type="button"
                  onClick={() => {
                    clearApiKey();
                    setApiKeyValue("");
                    setApiKeySaved(false);
                    setApiKeyMessage("Key cleared.");
                  }}
                  className="rounded-full border border-slate-700 px-3 py-1 text-[11px] text-slate-400"
                >
                  Clear Key
                </button>
                <span className="text-[11px] text-slate-500">
                  Status: {apiKeySaved ? "Stored" : "Not set"}
                </span>
              </div>
              {apiKeyMessage ? <p className="text-[11px] text-slate-400">{apiKeyMessage}</p> : null}
            </div>
          </div>
          <div className="rounded-xl border border-slate-800/60 p-4 text-sm text-slate-300">
            <p className="text-xs text-slate-400 mb-4">Live System Load</p>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-2">
                <p className="text-slate-400 text-xs uppercase tracking-[0.2em]">CPU</p>
                <p className="text-lg">{metrics?.cpu_percent ?? 0}%</p>
                <MeterBar value={metrics?.cpu_percent} color="#44f5a6" />
              </div>
              <div className="space-y-2">
                <p className="text-slate-400 text-xs uppercase tracking-[0.2em]">Memory</p>
                <p className="text-lg">
                  {metrics?.mem_used_gb ?? 0} / {metrics?.mem_total_gb ?? 0} GB
                </p>
                <MeterBar value={metrics?.mem_percent} color="#36c9f8" />
              </div>
              <div className="space-y-2">
                <p className="text-slate-400 text-xs uppercase tracking-[0.2em]">Disk</p>
                <p className="text-lg">
                  {metrics?.disk_used_gb ?? 0} / {metrics?.disk_total_gb ?? 0} GB
                </p>
                <MeterBar value={metrics?.disk_percent} color="#f5b94c" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
