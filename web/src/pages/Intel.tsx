import { Card } from "../components/ui/Card";
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

export default function Intel() {
  const { data } = useApi<IntelReport>("/api/intel/summary?region=Global", { interval: 60000 });

  return (
    <Card className="rounded-2xl p-6">
      <SectionHeader label="INTEL" title="Global Impact Summary" right={data?.risk_level ?? "Loading"} />
      <div className="mt-6 space-y-4 text-sm text-slate-300">
        {(data?.summary || ["No intel payload yet."]).map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
    </Card>
  );
}
