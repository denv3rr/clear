import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Label,
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
  color = "#48f1a6",
  title = "Portfolio value over time",
  description = "This chart shows how the selected portfolio value changed across the available history.",
  xLabel = "Date",
  yLabel = "Portfolio Value",
  valueFormatter = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}: {
  data: SeriesPoint[];
  height?: number;
  color?: string;
  title?: string;
  description?: string;
  xLabel?: string;
  yLabel?: string;
  valueFormatter?: (value: number) => string;
}) {
  const series = (data || []).map((point, idx) => ({
    idx,
    label:
      typeof point.ts === "number"
        ? new Date(point.ts < 1_000_000_000_000 ? point.ts * 1000 : point.ts).toLocaleDateString(
            undefined,
            { month: "short", day: "numeric" }
          )
        : `Point ${idx + 1}`,
    value: point.value
  }));

  return (
    <figure className="chart-figure" aria-label={title}>
      <figcaption>
        <strong>{title}</strong>
        <span>{description}</span>
      </figcaption>
      <div className="chart-panel" style={{ width: "100%", height, minHeight: height }}>
        <ResponsiveContainer width="100%" height="100%" minHeight={height} minWidth={120}>
          <AreaChart data={series} margin={{ top: 8, right: 12, bottom: 24, left: 8 }}>
          <defs>
            <linearGradient id="sparkGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.65} />
              <stop offset="100%" stopColor={color} stopOpacity={0.08} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="label"
            stroke="var(--slate-700)"
            tick={{ fill: "var(--slate-100)", fontSize: 10 }}
            minTickGap={28}
          >
            <Label value={xLabel} position="insideBottom" offset={-14} fill="var(--slate-200)" />
          </XAxis>
          <YAxis
            stroke="var(--slate-700)"
            tick={{ fill: "var(--slate-100)", fontSize: 10 }}
            domain={["auto", "auto"]}
            width={62}
          >
            <Label
              value={yLabel}
              angle={-90}
              position="insideLeft"
              style={{ textAnchor: "middle" }}
              fill="var(--slate-200)"
            />
          </YAxis>
          <Tooltip
            formatter={(value) => [valueFormatter(Number(value)), yLabel]}
            labelFormatter={(label) => `${xLabel}: ${label}`}
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
    </figure>
  );
}

export function DistributionBars({
  data,
  height = 200,
  color = "#2bdc98",
  title = "Portfolio return distribution",
  description = "This chart shows how often portfolio returns fell within each range.",
}: {
  data: DistributionBin[];
  height?: number;
  color?: string;
  title?: string;
  description?: string;
}) {
  const series = (data || []).map((bin) => ({
    label: `${(bin.bin_start * 100).toFixed(1)}% to ${(bin.bin_end * 100).toFixed(1)}%`,
    count: bin.count
  }));

  return (
    <figure className="chart-figure" aria-label={title}>
      <figcaption>
        <strong>{title}</strong>
        <span>{description}</span>
      </figcaption>
      <div className="chart-panel" style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={series} margin={{ top: 8, right: 12, bottom: 34, left: 8 }}>
          <XAxis
            dataKey="label"
            stroke="var(--slate-700)"
            tick={{ fill: "var(--slate-100)", fontSize: 10 }}
            interval="preserveStartEnd"
          >
            <Label value="Portfolio Return Range (%)" position="insideBottom" offset={-24} fill="var(--slate-200)" />
          </XAxis>
          <YAxis
            stroke="var(--slate-700)"
            tick={{ fill: "var(--slate-100)", fontSize: 10 }}
            allowDecimals={false}
          >
            <Label
              value="Observations"
              angle={-90}
              position="insideLeft"
              style={{ textAnchor: "middle" }}
              fill="var(--slate-200)"
            />
          </YAxis>
          <Tooltip
            formatter={(value) => [Number(value).toLocaleString(), "Observations"]}
            labelFormatter={(label) => `Portfolio return: ${label}`}
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
    </figure>
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
