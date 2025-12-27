import { useMemo, useState } from "react";
import { Card } from "../components/ui/Card";
import { SectionHeader } from "../components/ui/SectionHeader";
import { apiGet, useApi } from "../lib/api";

type ClientSummary = {
  client_id: string;
  name: string;
  accounts: number;
  total_value: number;
};

type ClientIndex = {
  clients: ClientSummary[];
};

type ReportPayload = {
  content: string;
  format: string;
};

export default function Reports() {
  const { data } = useApi<ClientIndex>("/api/clients", { interval: 60000 });
  const clients = data?.clients ?? [];
  const [selected, setSelected] = useState<ClientSummary | null>(null);
  const [report, setReport] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const clientLabel = useMemo(
    () => (selected ? `${selected.name} (${selected.client_id})` : "Select a client"),
    [selected]
  );

  const runReport = async (detail: boolean) => {
    if (!selected) return;
    setLoading(true);
    try {
      const payload = await apiGet<ReportPayload>(
        `/api/reports/client/${selected.client_id}?detail=${detail}&fmt=md`,
        0
      );
      setReport(payload.content || "");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="rounded-2xl p-6">
      <SectionHeader label="REPORTS" title="Client Reporting" right={clientLabel} />
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-3 text-sm text-slate-300">
          {clients.map((client) => (
            <button
              key={client.client_id}
              onClick={() => setSelected(client)}
              className={`w-full rounded-xl border px-4 py-3 text-left ${
                selected?.client_id === client.client_id
                  ? "border-emerald-400/60 text-slate-100"
                  : "border-slate-800/60 text-slate-300"
              }`}
            >
              <p className="font-medium">{client.name}</p>
              <p className="text-xs text-slate-400">{client.accounts} accounts</p>
            </button>
          ))}
        </div>
        <div className="lg:col-span-2 space-y-4">
          <div className="flex gap-3">
            <button
              onClick={() => runReport(false)}
              disabled={!selected || loading}
              className="px-4 py-2 rounded-lg border border-emerald-400/40 text-emerald-200 hover:bg-emerald-400/10 disabled:opacity-40"
            >
              Summary Report
            </button>
            <button
              onClick={() => runReport(true)}
              disabled={!selected || loading}
              className="px-4 py-2 rounded-lg border border-sky-400/40 text-sky-200 hover:bg-sky-400/10 disabled:opacity-40"
            >
              Detailed Report
            </button>
          </div>
          <div className="rounded-xl border border-slate-800/60 bg-ink-950/50 p-4 text-xs text-slate-300 whitespace-pre-wrap min-h-[220px]">
            {loading ? "Generating report..." : report || "Select a client to generate reports."}
          </div>
        </div>
      </div>
    </Card>
  );
}
