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
import { loadMapLibre } from "../lib/maplibre";
import type { MapLibre } from "../lib/maplibre";
import { Collapsible } from "../components/ui/Collapsible";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { KpiCard } from "../components/ui/KpiCard";
import { Reveal } from "../components/ui/Reveal";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useApi } from "../lib/api";
import { useMeasuredSize } from "../lib/useMeasuredSize";
import { useTrackerPause } from "../lib/trackerPause";
import { useTrackerStream } from "../lib/stream";
import {
  checkWorkerClass,
  preflightMapResources,
  preflightStyle
} from "../lib/mapDiagnostics";

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
  risk_series?: { label: string; value: number }[];
  news?: {
    sentiment_avg?: number;
    negative_ratio?: number;
    risk_score?: number;
  };
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
  const { ref: mapRef, size: mapSize } = useMeasuredSize<HTMLDivElement>();
  const mapInstance = useRef<MapLibre["Map"] | null>(null);
  const [maplibre, setMapLibre] = useState<MapLibre | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapStatus, setMapStatus] = useState("Initializing map...");
  const [mapFallback, setMapFallback] = useState(false);
  const [mapDiagnostics, setMapDiagnostics] = useState<string[]>([]);
  const leafletRef = useRef<HTMLDivElement | null>(null);
  const leafletMap = useRef<L.Map | null>(null);
  const leafletLayer = useRef<L.LayerGroup | null>(null);
  const [leafletStatus, setLeafletStatus] = useState("Initializing map...");
  const styleFallbackUsed = useRef(false);
  const styleRequested = useRef(false);
  const styleLoaded = useRef(false);
  const layersReadyRef = useRef(false);
  const mapReadyRef = useRef(false);
  const mapErrorRef = useRef<string | null>(null);
  const styleDataSeenRef = useRef(false);

  const [riskOpen, setRiskOpen] = useState(true);
  const [mapOpen, setMapOpen] = useState(true);
  const [feedOpen, setFeedOpen] = useState(true);
  const accentColor = "#48f1a6";
  const { paused } = useTrackerPause();
  const {
    data: trackerStream,
    connected: streamConnected,
    error: streamError,
    warnings: streamWarnings
  } = useTrackerStream<TrackerSnapshot>({
    interval: 5,
    mode: "combined"
  });
  const {
    data: trackerSnapshot,
    error: trackerError,
    warnings: trackerWarnings,
    refresh: refreshTrackers
  } = useApi<TrackerSnapshot>("/api/trackers/snapshot?mode=combined", {
    interval: 20000
  });
  const {
    data: intelSummary,
    error: intelError,
    warnings: intelWarnings,
    refresh: refreshIntel
  } = useApi<IntelSummary>("/api/intel/summary?region=Global", {
    interval: 30000
  });
  const activeSnapshot = trackerStream || trackerSnapshot;

  useEffect(() => {
    if (!paused) {
      refreshTrackers();
    }
  }, [paused, refreshTrackers]);

  const mapInitRef = useRef(false);
  const mapActiveRef = useRef(true);
  const mapResizeHandler = useRef<(() => void) | null>(null);

  useEffect(() => {
    let mounted = true;
    loadMapLibre()
      .then((lib) => {
        if (mounted) {
          setMapLibre(lib);
        }
      })
      .catch(() => {
        if (!mounted) return;
        setMapError("Map engine failed to load.");
        setMapStatus("Map engine failed.");
        setMapFallback(true);
      });
    return () => {
      mounted = false;
    };
  }, [maplibre]);

  useEffect(() => {
    let raf = 0;
    let timeout = 0;
    const initMap = () => {
      if (mapInitRef.current || mapInstance.current) return;
      if (!mapRef.current) {
        raf = window.requestAnimationFrame(initMap);
        return;
      }
      if (!maplibre) {
        setMapStatus("Loading map engine...");
        raf = window.requestAnimationFrame(initMap);
        return;
      }
      const rect = mapRef.current.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        setMapStatus("Waiting for map container...");
        raf = window.requestAnimationFrame(initMap);
        return;
      }
      mapInitRef.current = true;
      const canvas = document.createElement("canvas");
      const hasWebgl =
        !!window.WebGLRenderingContext &&
        (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"));
      if (!hasWebgl) {
        setMapError("WebGL not supported in this browser.");
        setMapStatus("WebGL not supported.");
        mapInitRef.current = false;
        return;
      }
      setMapStatus("Booting map engine...");
      const diagnostics: string[] = [];
      diagnostics.push(checkWorkerClass(maplibre));
      setMapDiagnostics(diagnostics);
      mapActiveRef.current = true;
      const styleUrl =
        "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
      preflightStyle(styleUrl).then((result) => {
        if (!mapActiveRef.current) return;
        setMapDiagnostics((prev) => {
          const next = prev.filter((item) => !item.startsWith("Style:"));
          next.push(`Style: ${result.ok ? "ok" : result.detail}`);
          return next;
        });
      });
      preflightMapResources(styleUrl).then((resourceLines) => {
        if (!mapActiveRef.current) return;
        setMapDiagnostics((prev) => {
          const next = prev.filter(
            (item) =>
              !item.startsWith("Sprite") &&
              !item.startsWith("Glyphs") &&
              !item.startsWith("Tile")
          );
          return [...next, ...resourceLines];
        });
      });
      let map: MapLibre["Map"];
      try {
        map = new maplibre.Map({
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
        mapInitRef.current = false;
        return;
      }
      setMapStatus("Map instance created.");
      map.addControl(new maplibre.NavigationControl({ visualizePitch: true }), "top-right");
      map.on("styledata", () => {
        styleDataSeenRef.current = true;
        setMapStatus("Loading style and tiles...");
      });
      const initLayers = () => {
        if (layersReadyRef.current) return;
        layersReadyRef.current = true;
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
            "circle-color": accentColor,
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
              accentColor
            ],
            "circle-opacity": 0.8
          }
        });
      };
      map.on("style.load", () => {
        styleLoaded.current = true;
        setMapStatus("Style loaded.");
        if (!mapReady) {
          setMapReady(true);
          mapReadyRef.current = true;
          setMapError(null);
          mapErrorRef.current = null;
          initLayers();
        }
      });
      map.on("render", () => {
        if (mapReady) {
          setMapStatus("Rendering map.");
        }
      });
      map.on("load", () => {
        setMapReady(true);
        mapReadyRef.current = true;
        setMapError(null);
        mapErrorRef.current = null;
        setMapStatus("Map ready.");
        map.resize();
        initLayers();
      });
      map.on("error", (event) => {
        const message = event?.error?.message;
        if (!styleFallbackUsed.current) {
          styleFallbackUsed.current = true;
          setMapStatus("Primary style blocked. Switching to fallback.");
          map.setStyle("https://demotiles.maplibre.org/style.json");
          return;
        }
        const detail = message || "Map data unavailable.";
        setMapError(detail);
        mapErrorRef.current = detail;
        setMapStatus("Map error.");
        setMapFallback(true);
      });
      mapInstance.current = map;
      timeout = window.setTimeout(() => {
        if (!mapReadyRef.current && !mapErrorRef.current) {
          if (!styleRequested.current) {
            setMapStatus("Style request blocked before fetch.");
          } else if (!styleLoaded.current) {
            setMapStatus("Style requested but never loaded.");
          } else {
            setMapStatus("Map load timeout. Check CSP/worker settings.");
          }
          setMapFallback(true);
          if (
            styleLoaded.current ||
            (styleDataSeenRef.current && map.isStyleLoaded && map.isStyleLoaded())
          ) {
            setMapReady(true);
            mapReadyRef.current = true;
            setMapError(null);
            mapErrorRef.current = null;
            initLayers();
            map.resize();
            map.triggerRepaint();
          }
        }
      }, 6000);
      const onResize = () => map.resize();
      mapResizeHandler.current = onResize;
      window.addEventListener("resize", onResize);
    };
    initMap();
    return () => {
      window.cancelAnimationFrame(raf);
      window.clearTimeout(timeout);
    };
  }, []);

  useEffect(() => {
    return () => {
      mapActiveRef.current = false;
      if (mapResizeHandler.current) {
        window.removeEventListener("resize", mapResizeHandler.current);
      }
      mapInstance.current?.remove();
      mapInstance.current = null;
      mapInitRef.current = false;
      setMapReady(false);
      mapReadyRef.current = false;
      setMapError(null);
      mapErrorRef.current = null;
      setMapStatus("Initializing map...");
    };
  }, []);

  useEffect(() => {
    if (!mapInstance.current || !mapReady) return;
    mapInstance.current.resize();
  }, [mapSize.height, mapSize.width, mapReady]);

  useEffect(() => {
    if (!mapInstance.current || !mapOpen) return;
    const handle = window.setTimeout(() => mapInstance.current?.resize(), 200);
    return () => window.clearTimeout(handle);
  }, [mapOpen]);

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
      const color = point.kind === "ship" ? "#8892a0" : accentColor;
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
    const source = map.getSource("tracker-points") as MapLibre["GeoJSONSource"] | undefined;
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

  useEffect(() => {
    if (!mapOpen) return;
    if (mapInstance.current) {
      mapInstance.current.resize();
    }
    if (leafletMap.current) {
      leafletMap.current.invalidateSize();
    }
  }, [mapOpen, mapFallback]);

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

  const noPoints = Boolean(activeSnapshot && activeSnapshot.points.length === 0);

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
        tone: "text-green-500"
      },
      {
        label: "Vessel Lanes",
        value: activeSnapshot
          ? `${activeSnapshot.points.filter((p) => p.kind === "ship").length}`
          : "—",
        tone: "text-green-400"
      },
      {
        label: "Risk Score",
        value: intelSummary?.risk_score !== undefined ? `${intelSummary.risk_score}/10` : "—",
        tone: "text-green-300"
      },
      {
        label: "Last Update",
        value: lastUpdated,
        tone: "text-green-300"
      }
    ],
    [intelSummary, activeSnapshot, lastUpdated]
  );

  const riskSeries = useMemo(() => {
    if (intelSummary?.risk_series?.length) {
      return intelSummary.risk_series.map((point) => ({
        day: point.label,
        value: point.value
      }));
    }
    return [];
  }, [intelSummary]);
  const hasRiskSeries = riskSeries.length > 0;

  const authHint = "Check CLEAR_WEB_API_KEY + localStorage clear_api_key.";
  const errorMessages = [
    paused ? "Tracker updates paused." : null,
    trackerError
      ? `Tracker snapshot failed: ${trackerError}${
          trackerError.includes("401") || trackerError.includes("403")
            ? ` (${authHint})`
            : ""
        }`
      : null,
    ...trackerWarnings.map((warning) => `Tracker snapshot: ${warning}`),
    streamError ? `Tracker stream failed: ${streamError}` : null,
    ...streamWarnings.map((warning) => `Tracker stream: ${warning}`),
    intelError
      ? `Intel summary failed: ${intelError}${
          intelError.includes("401") || intelError.includes("403")
            ? ` (${authHint})`
            : ""
        }`
      : null,
    ...intelWarnings.map((warning) => `Intel summary: ${warning}`)
  ].filter(Boolean) as string[];

  return (
    <>
      <Reveal>
        <header className="flex items-center justify-between">
          <div>
            <p className="tag text-xs text-slate-300">GLOBAL OVERVIEW</p>
            <h2 className="text-3xl font-semibold">Overview</h2>
          </div>
        </header>
      </Reveal>

      <Reveal delay={0.1}>
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {kpis.map((kpi) => (
            <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} tone={kpi.tone} />
          ))}
        </section>
      </Reveal>

      <Reveal delay={0.15}>
        <div className="mt-6">
          <ErrorBanner messages={errorMessages} onRetry={() => {
            refreshTrackers();
            refreshIntel();
          }} />
        </div>
      </Reveal>

      <Reveal delay={0.2}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div className="lg:col-span-2 space-y-6">
        <Collapsible
          title="Global Patterns"
          meta={intelSummary?.risk_level || "Live"}
          open={riskOpen}
          onToggle={() => setRiskOpen((prev) => !prev)}
        >
          <div className="h-52">
            {hasRiskSeries ? (
              <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={riskSeries}>
              <defs>
                <linearGradient id="riskGlow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--green-500)" stopOpacity={0.7} />
                  <stop offset="100%" stopColor="var(--green-500)" stopOpacity={0.11} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="day"
                stroke="var(--slate-700)"
                tick={{ fill: "var(--slate-100)", fontSize: 12 }}
              />
              <YAxis
                stroke="var(--slate-700)"
                tick={{ fill: "var(--slate-100)", fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--slate-900)",
                  border: "1px solid var(--slate-700)",
                  color: "var(--slate-100)"
                }}
              />
              <Area type="monotone" dataKey="value" stroke="var(--green-500)" fill="url(#riskGlow)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-slate-400">
            No risk series available.
          </div>
        )}
      </div>
    </Collapsible>

        <Collapsible
          title="Flight + Maritime Map"
          meta={mapFallback ? "Leaflet" : "MapLibre GL"}
          open={mapOpen}
          onToggle={() => setMapOpen((prev) => !prev)}
        >
          <div
            ref={mapRef}
            className="h-[300px] rounded-2xl overflow-hidden border border-slate-700 relative"
          >
        {mapFallback ? (
          <div ref={leafletRef} className="absolute inset-0" />
        ) : null}
        {!mapReady && !mapError && !mapFallback ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center text-xs text-slate-300 bg-slate-950/40">
            Loading map...
          </div>
        ) : null}
        {noPoints ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center text-xs text-slate-300 bg-slate-950/40">
            No tracker points in snapshot.
          </div>
        ) : null}
        {mapError && !mapFallback ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center text-xs text-amber-300 bg-slate-950/40">
            {mapError}
          </div>
        ) : null}
        <div className="absolute bottom-3 right-3 z-10 rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-2 text-[11px] text-slate-300">
          <p>{mapFallback ? leafletStatus : mapStatus}</p>
          {!mapFallback && mapDiagnostics.length ? (
            <div className="mt-1 space-y-0.5">
              {mapDiagnostics.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </Collapsible>
  </div>
  <div className="lg:col-span-1">
        <Collapsible
          title="Live Feed"
          meta={`${activeSnapshot ? activeSnapshot.count : 0} signals • ${
            streamConnected ? "Streaming" : "Snapshot"
          }`}
          open={feedOpen}
          onToggle={() => setFeedOpen((prev) => !prev)}
        >
          <div className="overflow-x-auto mt-2">
            {trackerRows.length ? (
              <table className="w-full text-sm">
            <thead className="text-slate-300 border-b border-slate-700">
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
                <tr key={row.id} className="border-b border-slate-800/60">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="py-3 pr-4 text-slate-100">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-xs text-slate-400">No live tracker data available.</p>
        )}
      </div>
    </Collapsible>
  </div>
</div>
      </Reveal>
    </>
  );
}
