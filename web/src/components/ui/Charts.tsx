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
    <div className="chart-panel" style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
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
              background: "#0b0e13",
              border: "1px solid #1f2937",
              color: "#e2e8f0"
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
          <XAxis dataKey="label" stroke="#334155" tick={{ fill: "#94a3b8", fontSize: 10 }} />
          <YAxis stroke="#334155" tick={{ fill: "#94a3b8", fontSize: 10 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: "#0b0e13",
              border: "1px solid #1f2937",
              color: "#e2e8f0"
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

  return (
    <div className="chart-panel" style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 6, right: 12, left: 12, bottom: 6 }}
        >
          <CartesianGrid stroke="#0f172a" strokeDasharray="2 4" />
          <XAxis type="number" domain={[0, max]} hide />
          <YAxis type="category" dataKey="name" hide />
          <Tooltip
            formatter={(val) => [`${Number(val).toFixed(1)}%`, "Load"]}
            contentStyle={{
              background: "#0b0e13",
              border: "1px solid #1f2937",
              color: "#e2e8f0"
            }}
          />
          <Bar
            dataKey="value"
            fill={color}
            radius={[8, 8, 8, 8]}
            background={{ fill: "#0f172a" }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
