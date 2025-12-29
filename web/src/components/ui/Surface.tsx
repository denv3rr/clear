import { motion } from "framer-motion";

type SurfaceProps = {
  title: string;
  data?: number[][];
  labels?: string[];
  className?: string;
};

function normalizeGrid(data?: number[][]) {
  if (!data || data.length === 0) return { max: 0, rows: [] as number[][] };
  const rows = data.map((row) => row.map((value) => (Number.isFinite(value) ? Number(value) : 0)));
  const max = rows.reduce((acc, row) => Math.max(acc, ...row), 0);
  return { max, rows };
}

export function SurfaceGrid({ title, data, labels, className = "" }: SurfaceProps) {
  const { max, rows } = normalizeGrid(data);
  const columns = rows[0]?.length ?? 0;
  const safeLabels = labels?.length === columns ? labels : null;

  return (
    <div className={`glass-panel rounded-2xl p-5 ${className}`}>
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-400">{title}</p>
        <p className="text-[11px] text-emerald-300">{columns ? `${rows.length}x${columns}` : "No data"}</p>
      </div>
      <div className="mt-3 space-y-2">
        {safeLabels ? (
          <div className="grid gap-2 text-[10px] text-slate-500" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
            {safeLabels.map((label) => (
              <span key={label} className="truncate">
                {label}
              </span>
            ))}
          </div>
        ) : null}
        <div
          className="surface-grid"
          style={{ gridTemplateColumns: `repeat(${Math.max(columns, 1)}, minmax(0, 1fr))` }}
        >
          {columns === 0 ? (
            <div className="surface-empty">Surface data unavailable.</div>
          ) : (
            rows.flatMap((row, rowIdx) =>
              row.map((value, colIdx) => {
                const intensity = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
                const height = 10 + intensity * 34;
                return (
                  <motion.div
                    key={`${rowIdx}-${colIdx}`}
                    className="surface-cell"
                    animate={{ height }}
                    transition={{ duration: 0.4, ease: "easeOut" }}
                    style={{
                      background: `linear-gradient(180deg, rgba(72,241,166,${0.15 + intensity * 0.35}), rgba(3,6,6,0.6))`,
                      borderColor: `rgba(72,241,166,${0.2 + intensity * 0.5})`,
                    }}
                    title={`${value.toFixed(3)}`}
                  />
                );
              })
            )
          )}
        </div>
      </div>
    </div>
  );
}
