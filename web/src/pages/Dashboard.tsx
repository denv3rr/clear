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
import L from "leaflet";
import maplibregl from "../lib/maplibre";
import { Card } from "../components/ui/Card";
import { KpiCard } from "../components/ui/KpiCard";
import { Reveal } from "../components/ui/Reveal";
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
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapStatus, setMapStatus] = useState("Initializing map...");
  const [mapFallback, setMapFallback] = useState(false);
  const leafletRef = useRef<HTMLDivElement | null>(null);
  const leafletMap = useRef<L.Map | null>(null);
  const leafletLayer = useRef<L.LayerGroup | null>(null);
  const [leafletStatus, setLeafletStatus] = useState("Initializing map...");
  const styleFallbackUsed = useRef(false);
  const styleRequested = useRef(false);
  const styleLoaded = useRef(false);

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
    const canvas = document.createElement("canvas");
    const hasWebgl =
      !!window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"));
    if (!hasWebgl) {
      setMapError("WebGL not supported in this browser.");
      setMapStatus("WebGL not supported.");
      return;
    }
    setMapStatus("Booting map engine...");
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: mapRef.current,
        style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        center: [0, 15],
        zoom: 1.5,
        attributionControl: false,
        transformRequest: (url, resourceType) => {
          if (resourceType === "Style" && !styleRequested.current) {
            styleRequested.current = true;
            setMapStatus("Requesting style...");
          }
          return { url };
        }
      });
    } catch (err) {
      setMapError(err instanceof Error ? err.message : "Map initialization failed.");
      setMapStatus("Map init failed.");
      return;
    }
    setMapStatus("Map instance created.");
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("styledata", () => {
      setMapStatus("Loading style and tiles...");
    });
    map.on("style.load", () => {
      styleLoaded.current = true;
      setMapStatus("Style loaded.");
    });
    map.on("render", () => {
      if (mapReady) {
        setMapStatus("Rendering map.");
      }
    });
    map.on("load", () => {
      setMapReady(true);
      setMapError(null);
      setMapStatus("Map ready.");
      map.resize();
      map.addSource("tracker-points", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });
      map.addLayer({
        id: "tracker-points-glow",
        type: "circle",
        source: "tracker-points",
        paint: {
          "circle-radius": 6,
          "circle-color": "#48f1a6",
          "circle-opacity": 0.12
        }
      });
      map.addLayer({
        id: "tracker-points-layer",
        type: "circle",
        source: "tracker-points",
        paint: {
          "circle-radius": 3,
          "circle-color": [
            "match",
            ["get", "kind"],
            "ship",
            "#8892a0",
            "#48f1a6"
          ],
          "circle-opacity": 0.8
        }
      });
    });
    map.on("error", (event) => {
      const message = event?.error?.message;
      if (!styleFallbackUsed.current) {
        styleFallbackUsed.current = true;
        setMapStatus("Primary style blocked. Switching to fallback.");
        map.setStyle("https://demotiles.maplibre.org/style.json");
        return;
      }
      setMapError(message || "Map data unavailable.");
      setMapStatus("Map error.");
      setMapFallback(true);
    });
    mapInstance.current = map;
    const timeout = window.setTimeout(() => {
      if (!mapReady && !mapError) {
        if (!styleRequested.current) {
          setMapStatus("Style request blocked before fetch.");
        } else if (!styleLoaded.current) {
          setMapStatus("Style requested but never loaded.");
        } else {
          setMapStatus("Map load timeout. Check CSP/worker settings.");
        }
        setMapFallback(true);
      }
    }, 6000);
    return () => {
      window.clearTimeout(timeout);
      map.remove();
    };
  }, []);

  useEffect(() => {
    if (!mapFallback || !leafletRef.current || leafletMap.current) return;
    setLeafletStatus("Booting fallback map...");
    const map = L.map(leafletRef.current, { center: [15, 0], zoom: 2 });
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    });
    tiles.on("tileerror", () => {
      setLeafletStatus("Tile load error. Check CSP or network.");
    });
    tiles.addTo(map);
    const layer = L.layerGroup().addTo(map);
    leafletMap.current = map;
    leafletLayer.current = layer;
    setLeafletStatus("Fallback map ready.");
  }, [mapFallback]);

  useEffect(() => {
    if (!leafletLayer.current || !leafletMap.current || !activeSnapshot?.points)
      return;
    const layer = leafletLayer.current;
    layer.clearLayers();
    const points = activeSnapshot.points.filter(
      (point) => Number.isFinite(point.lat) && Number.isFinite(point.lon)
    );
    points.slice(0, 200).forEach((point) => {
      const color = point.kind === "ship" ? "#8892a0" : "#48f1a6";
      L.circleMarker([point.lat, point.lon], {
        radius: 4,
        color,
        weight: 1,
        opacity: 0.9,
        fillColor: color,
        fillOpacity: 0.6
      }).addTo(layer);
    });
    if (points.length) {
      const bounds = L.latLngBounds(points.map((point) => [point.lat, point.lon]));
      leafletMap.current.fitBounds(bounds, { padding: [30, 30], maxZoom: 5 });
    }
  }, [activeSnapshot, mapFallback]);

  useEffect(() => {
    if (!mapInstance.current || !mapReady || !activeSnapshot?.points) return;
    const map = mapInstance.current;
    const source = map.getSource("tracker-points") as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    const features = activeSnapshot.points
      .filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lon))
      .slice(0, 120)
      .map((point) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [point.lon, point.lat]
        },
        properties: {
          kind: point.kind,
          label: point.label
        }
      }));
    source.setData({ type: "FeatureCollection", features });
  }, [activeSnapshot, mapReady]);

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
      <Reveal>
        <header className="flex items-center justify-between">
          <div>
            <p className="tag text-xs text-slate-400">GLOBAL RISK</p>
            <h2 className="text-3xl font-semibold">Trackers</h2>
          </div>
        </header>
      </Reveal>

      <Reveal delay={0.1}>
        <section className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {kpis.map((kpi) => (
            <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} tone={kpi.tone} />
          ))}
        </section>
      </Reveal>

      <Reveal delay={0.15}>
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="rounded-2xl p-6 lg:col-span-2 min-h-[360px] relative overflow-hidden">
            <SectionHeader label="MAPS" title="Flight + Maritime Layer" right="MapLibre GL" />
            <div className="mt-6 h-[260px] rounded-2xl overflow-hidden border border-slate-800 relative">
              <div ref={mapRef} className="absolute inset-0" />
              {mapFallback ? (
                <div ref={leafletRef} className="absolute inset-0" />
              ) : null}
              {!mapReady && !mapError && !mapFallback ? (
                <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-400 bg-ink-950/40">
                  Loading map...
                </div>
              ) : null}
              {mapError && !mapFallback ? (
                <div className="absolute inset-0 flex items-center justify-center text-xs text-amber-300 bg-ink-950/40">
                  {mapError}
                </div>
              ) : null}
              <div className="absolute bottom-3 right-3 rounded-lg border border-slate-800/60 bg-ink-950/80 px-3 py-2 text-[11px] text-slate-400">
                {mapFallback ? leafletStatus : mapStatus}
              </div>
            </div>
            <div className="absolute -bottom-16 -right-12 h-40 w-40 rounded-full bg-emerald-400/20 blur-3xl" />
          </Card>

          <Card className="rounded-2xl p-6 flex flex-col">
            <SectionHeader label="RISK SIGNALS" title="Global Patterns" />
            <div className="mt-4 h-52">
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
      </Reveal>

      <Reveal delay={0.2}>
        <Card className="rounded-2xl p-6">
          <SectionHeader
            label="LIVE FEED"
            title="Tracker Signals"
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
      </Reveal>
    </>
  );
}
