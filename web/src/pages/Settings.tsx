import { Card } from "../components/ui/Card";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useApi } from "../lib/api";

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
  error?: string | null;
};

export default function Settings() {
  const { data } = useApi<SettingsPayload>("/api/settings", { interval: 60000 });

  return (
    <Card className="rounded-2xl p-6">
      <SectionHeader label="SETTINGS" title="System Settings Snapshot" />
      <div className="mt-6 text-sm text-slate-300 space-y-3">
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
    </Card>
  );
}
