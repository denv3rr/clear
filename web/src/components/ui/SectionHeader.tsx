type SectionHeaderProps = {
  label: string;
  title: string;
  right?: React.ReactNode;
};

export function SectionHeader({ label, title, right }: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="tag text-xs text-slate-400">{label}</p>
        <h3 className="text-xl font-semibold">{title}</h3>
      </div>
      {right ? <div className="text-xs text-emerald-300">{right}</div> : null}
    </div>
  );
}
