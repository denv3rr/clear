type SectionHeaderProps = {
  label: string;
  title: string;
  right?: React.ReactNode;
};

export function SectionHeader({ label, title, right }: SectionHeaderProps) {
  return (
    <div className="flex items-end justify-between gap-6">
      <div className="space-y-1">
        <p className="tag text-[11px] uppercase tracking-[0.2em] text-slate-500">{label}</p>
        <h3 className="text-lg font-semibold text-slate-100 md:text-xl">{title}</h3>
      </div>
      {right ? <div className="text-xs text-emerald-300">{right}</div> : null}
    </div>
  );
}
