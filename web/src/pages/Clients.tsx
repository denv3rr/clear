import { Card } from "../components/ui/Card";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useApi } from "../lib/api";

type ClientSummary = {
  client_id: string;
  name: string;
  accounts: number;
  total_value: number;
};

type ClientIndex = {
  clients: ClientSummary[];
};

export default function Clients() {
  const { data } = useApi<ClientIndex>("/api/clients", { interval: 60000 });
  const rows = data?.clients ?? [];

  return (
    <Card className="rounded-2xl p-6">
      <SectionHeader label="CLIENTS" title="Portfolio Directory" right={`${rows.length} clients`} />
      <div className="mt-6 space-y-3 text-sm text-slate-300">
        {rows.length === 0 ? (
          <p>No client profiles loaded.</p>
        ) : (
          rows.map((client) => (
            <div key={client.client_id} className="flex items-center justify-between border-b border-slate-900/60 py-2">
              <div>
                <p className="text-slate-100 font-medium">{client.name}</p>
                <p className="text-xs text-slate-400">{client.client_id}</p>
              </div>
              <div className="text-right">
                <p>{client.accounts} accounts</p>
                <p className="text-xs text-slate-400">${client.total_value.toFixed(2)}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
