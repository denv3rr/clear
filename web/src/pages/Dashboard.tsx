import { useEffect, useMemo, useRef, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable
} from "@tanstack/react-table";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import maplibregl from "maplibre-gl";
import { Card } from "../components/ui/Card";
import { KpiCard } from "../components/ui/KpiCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useApi } from "../lib/api";
import { useTrackerStream } from "../lib/stream";

type TrackerRow = {
  type: string;
  category: string;
  label: string;
  country: string;
  speed: number;
  altitude: number;
  heat: number;
};

type TrackerPoint = {
  kind: string;
  category: string;
  label: string;
  lat: number;
  lon: number;
  altitude_ft: number | null;
  speed_kts: number | null;
  country: string | null;
  speed_heat: number | null;
};

type TrackerSnapshot = {
  count: number;
  warnings: string[];
  points: TrackerPoint[];
};

type IntelSummary = {
  risk_level?: string;
  risk_score?: number;
  confidence?: string;
};

const columns: ColumnDef<TrackerRow>[] = [
  { accessorKey: "type", header: "Type" },
  { accessorKey: "category", header: "Category" },
  { accessorKey: "label", header: "Label" },
  { accessorKey: "country", header: "Country" },
  { accessorKey: "speed", header: "Speed" },
  { accessorKey: "altitude", header: "Alt(ft)" },
  { accessorKey: "heat", header: "Heat" }
];

export default function Dashboard() {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapInstance = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  const { data: trackerStream } = useTrackerStream<TrackerSnapshot>({ interval: 5, mode: "combined" });
  const { data: trackerSnapshot } = useApi<TrackerSnapshot>("/api/trackers/snapshot?mode=combined", {
    interval: 20000
  });
  const { data: intelSummary } = useApi<IntelSummary>("/api/intel/summary?region=Global", {
    interval: 30000
  });
  const activeSnapshot = trackerStream || trackerSnapshot;

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;
    const map = new maplibregl.Map({
      container: mapRef.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: [0, 15],
      zoom: 1.5,
      attributionControl: false
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("load", () => {
      setMapReady(true);
      setMapError(null);
      map.resize();
    });
    map.on("error", () => {
      setMapError("Map data unavailable.");
    });
    mapInstance.current = map;
    return () => map.remove();
  }, []);

  useEffect(() => {
    if (!mapInstance.current || !activeSnapshot?.points) return;
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = activeSnapshot.points.slice(0, 80).map((point) => {
      const el = document.createElement("div");
      el.className =
        "h-2 w-2 rounded-full " + (point.kind === "ship" ? "bg-sky-400" : "bg-emerald-400");
      return new maplibregl.Marker({ element: el })
        .setLngLat([point.lon, point.lat])
        .addTo(mapInstance.current as maplibregl.Map);
    });
  }, [activeSnapshot]);

  const trackerRows = useMemo<TrackerRow[]>(() => {
    if (!activeSnapshot?.points) return [];
    return activeSnapshot.points.slice(0, 40).map((point) => ({
      type: point.kind === "ship" ? "Vessel" : "Flight",
      category: point.category || "-",
      label: point.label || "-",
      country: point.country || "-",
      speed: Math.round(point.speed_kts || 0),
      altitude: Math.round(point.altitude_ft || 0),
      heat: Number((point.speed_heat || 0).toFixed(2))
    }));
  }, [activeSnapshot]);

  const table = useReactTable({
    data: trackerRows,
    columns,
    getCoreRowModel: getCoreRowModel()
  });

  const lastUpdated = useMemo(() => new Date().toLocaleTimeString(), [activeSnapshot]);

  const kpis = useMemo(
    () => [
      {
        label: "Active Flights",
        value: activeSnapshot
          ? `${activeSnapshot.points.filter((p) => p.kind === "flight").length}`
          : "—",
        tone: "text-neon-500"
      },
      {
        label: "Vessel Lanes",
        value: activeSnapshot
          ? `${activeSnapshot.points.filter((p) => p.kind === "ship").length}`
          : "—",
        tone: "text-sky-300"
      },
      {
        label: "Risk Score",
        value: intelSummary?.risk_score !== undefined ? `${intelSummary.risk_score}/10` : "—",
        tone: "text-ember-500"
      },
      {
        label: "Last Update",
        value: lastUpdated,
        tone: "text-emerald-300"
      }
    ],
    [intelSummary, activeSnapshot, lastUpdated]
  );

  const riskSeries = useMemo(() => {
    const value = intelSummary?.risk_score ?? 0;
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => ({
      day,
      value
    }));
  }, [intelSummary]);

  return (
    <>
      <header className="flex items-center justify-between">
        <div>
          <p className="tag text-xs text-slate-400">GLOBAL RISK OVERVIEW</p>
          <h2 className="text-3xl font-semibold">Global Tracker Dashboard</h2>
        </div>
        <button className="px-5 py-3 rounded-xl bg-emerald-400/20 border border-emerald-400/40 text-emerald-300 hover:bg-emerald-400/30 transition">
          Open Live View
        </button>
      </header>

      <section className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} tone={kpi.tone} />
        ))}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="rounded-2xl p-6 lg:col-span-2 min-h-[360px] relative overflow-hidden">
          <SectionHeader label="GLOBAL MAP" title="Flight + Maritime Layer" right="MapLibre GL" />
          <div className="mt-6 h-[260px] rounded-2xl overflow-hidden border border-slate-800 relative">
            <div ref={mapRef} className="absolute inset-0" />
            {!mapReady && !mapError ? (
              <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-400 bg-ink-950/40">
                Loading map...
              </div>
            ) : null}
            {mapError ? (
              <div className="absolute inset-0 flex items-center justify-center text-xs text-amber-300 bg-ink-950/40">
                {mapError}
              </div>
            ) : null}
          </div>
          <div className="absolute -bottom-16 -right-12 h-40 w-40 rounded-full bg-emerald-400/20 blur-3xl" />
        </Card>

        <Card className="rounded-2xl p-6 flex flex-col">
          <SectionHeader label="RISK SIGNALS" title="Global Patterns" />
          <div className="flex-1 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={riskSeries}>
                <defs>
                  <linearGradient id="riskGlow" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#48f1a6" stopOpacity={0.7} />
                    <stop offset="100%" stopColor="#48f1a6" stopOpacity={0.11} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" stroke="#334155" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <YAxis stroke="#334155" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: "#0b0e13",
                    border: "1px solid #1f2937",
                    color: "#e2e8f0"
                  }}
                />
                <Area type="monotone" dataKey="value" stroke="#48f1a6" fill="url(#riskGlow)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </section>

      <Card className="rounded-2xl p-6">
        <SectionHeader
          label="LIVE FEED"
          title="Tracker Intelligence"
          right={activeSnapshot ? `${activeSnapshot.count} signals` : "Loading"}
        />
        <div className="overflow-x-auto mt-6">
          <table className="w-full text-sm">
            <thead className="text-slate-400 border-b border-slate-800">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th key={header.id} className="py-3 text-left font-medium">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b border-slate-900/60">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="py-3 pr-4 text-slate-200">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
