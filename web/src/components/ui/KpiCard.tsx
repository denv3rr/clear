type KpiCardProps = {
  label: string;
  value: string;
  tone?: string;
};

export function KpiCard({ label, value, tone = "text-slate-200" }: KpiCardProps) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-800/60 bg-slate-900/60 p-6">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900/50 to-slate-950/50" />
      <div className="relative">
        <p className="tag text-xs text-slate-400">{label}</p>
        <p className={`text-4xl font-semibold mt-4 ${tone}`}>{value}</p>
      </div>
    </div>
  );
}
