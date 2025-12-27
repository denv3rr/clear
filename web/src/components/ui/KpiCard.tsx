type KpiCardProps = {
  label: string;
  value: string;
  tone?: string;
};

export function KpiCard({ label, value, tone = "text-slate-200" }: KpiCardProps) {
  return (
    <div className="glass-panel rounded-2xl p-5">
      <p className="tag text-xs text-slate-400">{label}</p>
      <p className={`text-3xl font-semibold mt-3 ${tone}`}>{value}</p>
    </div>
  );
}
