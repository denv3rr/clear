import { Card } from "../components/ui/Card";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useApi } from "../lib/api";

type DiagnosticsPayload = {
  system: {
    hostname?: string;
    ip?: string;
    os?: string;
    cpu_usage?: string;
    mem_usage?: string;
    python_version?: string;
  };
  disk: {
    total_gb: number;
    used_gb: number;
    free_gb: number;
  };
};

export default function Tools() {
  const { data } = useApi<DiagnosticsPayload>("/api/tools/diagnostics", { interval: 60000 });

  return (
    <Card className="rounded-2xl p-6">
      <SectionHeader label="TOOLS" title="Diagnostics" />
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6 text-sm text-slate-300">
        <div className="space-y-2">
          <p className="text-slate-100 font-medium">System</p>
          <p>Host: {data?.system?.hostname || "—"}</p>
          <p>IP: {data?.system?.ip || "—"}</p>
          <p>OS: {data?.system?.os || "—"}</p>
          <p>CPU: {data?.system?.cpu_usage || "—"}</p>
          <p>Memory: {data?.system?.mem_usage || "—"}</p>
          <p>Python: {data?.system?.python_version || "—"}</p>
        </div>
        <div className="space-y-2">
          <p className="text-slate-100 font-medium">Disk</p>
          <p>Total: {data?.disk?.total_gb?.toFixed(2) ?? "—"} GB</p>
          <p>Used: {data?.disk?.used_gb?.toFixed(2) ?? "—"} GB</p>
          <p>Free: {data?.disk?.free_gb?.toFixed(2) ?? "—"} GB</p>
        </div>
      </div>
    </Card>
  );
}
