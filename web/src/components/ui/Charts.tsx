import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { useMeasuredSize } from "../../lib/useMeasuredSize";

type SeriesPoint = {
  ts: number | null;
  value: number;
};

type DistributionBin = {
  bin_start: number;
  bin_end: number;
  count: number;
};

type MeterPoint = {
  name: string;
  value: number;
};

export function AreaSparkline({
  data,
  height = 220,
  color = "#48f1a6"
}: {
  data: SeriesPoint[];
  height?: number;
  color?: string;
}) {
  const series = (data || []).map((point, idx) => ({
    idx,
    value: point.value
  }));

  return (
    <div className="chart-panel" style={{ width: "100%", height, minHeight: height }}>
      <ResponsiveContainer width="100%" height="100%" minHeight={height} minWidth={120}>
        <AreaChart data={series}>
          <defs>
            <linearGradient id="sparkGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.65} />
              <stop offset="100%" stopColor={color} stopOpacity={0.08} />
            </linearGradient>
          </defs>
          <XAxis dataKey="idx" hide />
          <YAxis hide domain={["auto", "auto"]} />
          <Tooltip
            contentStyle={{
              background: "var(--slate-900)",
              border: "1px solid var(--slate-700)",
              color: "var(--slate-100)"
            }}
          />
          <Area type="monotone" dataKey="value" stroke={color} fill="url(#sparkGlow)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DistributionBars({
  data,
  height = 200,
  color = "#2bdc98"
}: {
  data: DistributionBin[];
  height?: number;
  color?: string;
}) {
  const series = (data || []).map((bin) => ({
    label: `${(bin.bin_start * 100).toFixed(1)}%`,
    count: bin.count
  }));

  return (
    <div className="chart-panel" style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={series}>
          <XAxis dataKey="label" stroke="var(--slate-700)" tick={{ fill: "var(--slate-100)", fontSize: 10 }} />
          <YAxis stroke="var(--slate-700)" tick={{ fill: "var(--slate-100)", fontSize: 10 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: "var(--slate-900)",
              border: "1px solid var(--slate-700)",
              color: "var(--slate-100)"
            }}
          />
          <Bar dataKey="count" fill={color} radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MeterBar({
  value,
  height = 70,
  color = "#48f1a6",
  max = 100
}: {
  value?: number | null;
  height?: number;
  color?: string;
  max?: number;
}) {
  const safeValue =
    typeof value === "number" && Number.isFinite(value)
      ? Math.min(Math.max(value, 0), max)
      : 0;
  const data: MeterPoint[] = [{ name: "util", value: safeValue }];
  const { ref, size } = useMeasuredSize<HTMLDivElement>();
  const visible = ref.current ? ref.current.offsetParent !== null : false;
  const ready = visible && size.width > 0 && size.height > 0;

  return (
    <div
      ref={ref}
      className="chart-panel"
      style={{ width: "100%", height, minHeight: height }}
    >
      {ready ? (
        <ResponsiveContainer width="100%" height="100%" minHeight={height} minWidth={120}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 6, right: 12, left: 12, bottom: 6 }}
          >
            <CartesianGrid stroke="var(--slate-900)" strokeDasharray="2 4" />
            <XAxis type="number" domain={[0, max]} hide />
            <YAxis type="category" dataKey="name" hide />
            <Tooltip
              formatter={(val) => [`${Number(val).toFixed(1)}%`, "Load"]}
              contentStyle={{
                background: "var(--slate-900)",
                border: "1px solid var(--slate-700)",
                color: "var(--slate-100)"
              }}
            />
            <Bar
              dataKey="value"
              fill={color}
              radius={[8, 8, 8, 8]}
              background={{ fill: "var(--slate-900)" }}
            />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-full w-full" />
      )}
    </div>
  );
}
