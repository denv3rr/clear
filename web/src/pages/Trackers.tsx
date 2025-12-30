import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import maplibregl from "../lib/maplibre";
import { Card } from "../components/ui/Card";
import { Collapsible } from "../components/ui/Collapsible";
import { ErrorBanner } from "../components/ui/ErrorBanner";
import { KpiCard } from "../components/ui/KpiCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { apiGet, useApi } from "../lib/api";
import { useMeasuredSize } from "../lib/useMeasuredSize";
import { useTrackerPause } from "../lib/trackerPause";
import { useTrackerStream } from "../lib/stream";
import {
  checkWorkerClass,
  preflightMapResources,
  preflightStyle
} from "../lib/mapDiagnostics";

type TrackerSnapshot = {
  count: number;
  warnings: string[];
  points: {
    id?: string;
    kind: string;
    label: string;
    category: string;
    lat?: number;
    lon?: number;
    country?: string | null;
    operator?: string | null;
    operator_name?: string | null;
    flight_number?: string | null;
    tail_number?: string | null;
  }[];
};

type SearchResult = {
  count: number;
  points: {
    id: string;
    kind: string;
    label: string;
    category: string;
    operator?: string | null;
    operator_name?: string | null;
    flight_number?: string | null;
  }[];
};

type HistoryPoint = {
  ts: number;
  lat: number;
  lon: number;
  speed_kts: number | null;
};

type TrackerHistory = {
  id: string;
  history: HistoryPoint[];
  summary?: {
    points?: number;
    distance_km?: number;
    start?: { lat: number; lon: number; ts: number };
    end?: { lat: number; lon: number; ts: number };
    direction?: string;
    bearing_deg?: number;
    avg_speed_kts?: number | null;
    avg_altitude_ft?: number | null;
    duration_sec?: number | null;
    route_hint?: string;
  };
};

type TrackerDetail = {
  id: string;
  point?: {
    id?: string;
    label?: string;
    category?: string;
    kind?: string;
    icao24?: string | null;
    callsign?: string | null;
    operator?: string | null;
    operator_name?: string | null;
    flight_number?: string | null;
    tail_number?: string | null;
    country?: string | null;
    altitude_ft?: number | null;
    speed_kts?: number | null;
  };
  history: HistoryPoint[];
  summary?: TrackerHistory["summary"];
};

export default function Trackers() {
  const [mode, setMode] = useState<"combined" | "flights" | "ships">("combined");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [includeCommercial, setIncludeCommercial] = useState(false);
  const [includePrivate, setIncludePrivate] = useState(false);
  const [countryFilter, setCountryFilter] = useState("");
  const [operatorFilter, setOperatorFilter] = useState("");
  const [idFilter, setIdFilter] = useState("");
  const {
    data: streamData,
    connected,
    error: streamError
  } = useTrackerStream<TrackerSnapshot>({
    interval: 5,
    mode
  });
  const { paused } = useTrackerPause();
  const {
    data: pollData,
    error: pollError,
    refresh: refreshPoll
  } = useApi<TrackerSnapshot>(`/api/trackers/snapshot?mode=${mode}`, { interval: 20000 });
  const data = streamData || pollData;
  const points = data?.points || [];
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TrackerDetail | null>(null);
  const history = detail ? { id: detail.id, history: detail.history, summary: detail.summary } : null;
  const { ref: mapRef, size: mapSize } = useMeasuredSize<HTMLDivElement>();
  const mapInstance = useRef<maplibregl.Map | null>(null);
  const styleFallbackUsed = useRef(false);
  const styleRequested = useRef(false);
  const styleLoaded = useRef(false);
  const layersReadyRef = useRef(false);
  const mapReadyRef = useRef(false);
  const mapErrorRef = useRef<string | null>(null);
  const styleDataSeenRef = useRef(false);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapStatus, setMapStatus] = useState("Initializing map...");
  const [mapDiagnostics, setMapDiagnostics] = useState<string[]>([]);
  const leafletRef = useRef<HTMLDivElement | null>(null);
  const leafletMap = useRef<L.Map | null>(null);
  const leafletLayer = useRef<L.LayerGroup | null>(null);
  const [leafletStatus, setLeafletStatus] = useState("Initializing map...");
  const [riskOpen, setRiskOpen] = useState(true);
  const [mapOpen, setMapOpen] = useState(true);
  const [feedOpen, setFeedOpen] = useState(true);

  const searchPath = useMemo(() => {
    const kindParam = mode === "combined" ? "" : `&kind=${mode === "ships" ? "ship" : "flight"}`;
    return `/api/trackers/search?q=${encodeURIComponent(query)}&limit=12&mode=${mode}${kindParam}`;
  }, [query, mode]);
  const { data: searchResults, error: searchError } = useApi<SearchResult>(searchPath, {
    enabled: query.trim().length > 1
  });
  const filteredSearchResults = useMemo(() => {
    if (!searchResults) return null;
    let next = searchResults.points;
    if (!includeCommercial) {
      next = next.filter((point) => !(point.kind === "flight" && point.category === "commercial"));
    }
    if (!includePrivate) {
      next = next.filter((point) => !(point.kind === "flight" && point.category === "private"));
    }
    if (categoryFilter !== "all") {
      next = next.filter((point) => point.category === categoryFilter);
    }
    return { ...searchResults, points: next, count: next.length };
  }, [searchResults, includeCommercial, includePrivate, categoryFilter]);
  const authHint = "Check CLEAR_WEB_API_KEY + localStorage clear_api_key.";
  const errorMessages = [
    paused ? "Tracker updates paused." : null,
    pollError
      ? `Tracker snapshot failed: ${pollError}${
          pollError.includes("401") || pollError.includes("403") ? ` (${authHint})` : ""
        }`
      : null,
    streamError ? `Tracker stream failed: ${streamError}` : null,
    searchError ? `Search failed: ${searchError}` : null
  ].filter(Boolean) as string[];
  const filteredPoints = useMemo(() => {
    let next = points;
    if (mode !== "combined") {
      const wanted = mode === "ships" ? "ship" : "flight";
      next = next.filter((point) => point.kind === wanted);
    }
    if (!includeCommercial) {
      next = next.filter((point) => !(point.kind === "flight" && point.category === "commercial"));
    }
    if (!includePrivate) {
      next = next.filter((point) => !(point.kind === "flight" && point.category === "private"));
    }
    if (categoryFilter !== "all") {
      next = next.filter((point) => point.category === categoryFilter);
    }
    if (countryFilter.trim()) {
      const needle = countryFilter.trim().toLowerCase();
      next = next.filter((point) => (point.country || "").toLowerCase().includes(needle));
    }
    if (operatorFilter.trim()) {
      const needle = operatorFilter.trim().toLowerCase();
      next = next.filter((point) => {
        const op = point.operator || "";
        const opName = point.operator_name || "";
        return op.toLowerCase().includes(needle) || opName.toLowerCase().includes(needle);
      });
    }
    if (idFilter.trim()) {
      const needle = idFilter.trim().toLowerCase();
      next = next.filter((point) => {
        const label = point.label || "";
        const id = point.id || "";
        const flight = point.flight_number || "";
        const tail = point.tail_number || "";
        return (
          label.toLowerCase().includes(needle) ||
          id.toLowerCase().includes(needle) ||
          flight.toLowerCase().includes(needle) ||
          tail.toLowerCase().includes(needle)
        );
      });
    }
    return next;
  }, [
    points,
    mode,
    includeCommercial,
    includePrivate,
    categoryFilter,
    countryFilter,
    operatorFilter,
    idFilter
  ]);
  const categories = useMemo(() => {
    const entries = Array.from(new Set(points.map((point) => point.category).filter(Boolean)));
    const reserved = ["military", "government"];
    const sorted = entries.filter((entry) => !reserved.includes(entry)).sort();
    const list = ["all", ...reserved, ...sorted];
    return Array.from(new Set(list));
  }, [points]);
  const riskTotals = useMemo(() => {
    const counts = filteredPoints.reduce(
      (acc, point) => {
        if (point.kind === "flight") acc.flights += 1;
        if (point.kind === "ship") acc.ships += 1;
        return acc;
      },
      { flights: 0, ships: 0 }
    );
    const categoryMap = filteredPoints.reduce<Record<string, number>>((acc, point) => {
      const key = point.category || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const topCategories = Object.entries(categoryMap)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);
    return { counts, topCategories };
  }, [filteredPoints]);

  const trackerGeojson = useMemo(() => {
    return {
      type: "FeatureCollection",
      features: filteredPoints
        .filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lon))
        .map((point) => ({
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [point.lon as number, point.lat as number]
          },
          properties: {
            id: point.id || "",
            kind: point.kind,
            label: point.label,
            category: point.category
          }
        }))
    };
  }, [filteredPoints]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    if (paused) {
      setDetail(null);
      return;
    }
    apiGet<TrackerDetail>(`/api/trackers/detail/${encodeURIComponent(selectedId)}`, 0)
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [selectedId, paused]);

  const mapInitRef = useRef(false);
  const mapActiveRef = useRef(true);
  const mapResizeHandler = useRef<(() => void) | null>(null);

  useEffect(() => {
    let raf = 0;
    let timeout = 0;
    const initMap = () => {
      if (mapInitRef.current || mapInstance.current) return;
      if (!mapRef.current) {
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
    diagnostics.push(checkWorkerClass(maplibregl));
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
      let map: maplibregl.Map;
      try {
        map = new maplibregl.Map({
          container: mapRef.current,
          style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
          center: [0, 15],
          zoom: 1.4,
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
      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
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
        map.on("mouseenter", "tracker-points-layer", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "tracker-points-layer", () => {
          map.getCanvas().style.cursor = "";
        });
        map.on("click", "tracker-points-layer", (event) => {
          const feature = event.features?.[0];
          const id = feature?.properties?.id as string | undefined;
          if (id) {
            setSelectedId(id);
            setFeedOpen(true);
          }
        });
        map.addSource("history-line", {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: { type: "LineString", coordinates: [] },
            properties: {}
          }
        });
        map.addLayer({
          id: "history-line-layer",
          type: "line",
          source: "history-line",
          paint: {
            "line-color": "#48f1a6",
            "line-width": 2,
            "line-opacity": 0.8
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
        window.setTimeout(() => map.resize(), 200);
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
      });
      map.on("idle", () => {
        if (!mapError) {
          setMapError(null);
          setMapStatus("Map idle.");
        }
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
    if (!leafletRef.current || leafletMap.current) return;
    setLeafletStatus("Booting map engine...");
    const map = L.map(leafletRef.current, {
      center: [15, 0],
      zoom: 2,
      zoomControl: true
    });
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
    setLeafletStatus("Map ready.");
  }, []);

  useEffect(() => {
    if (!mapInstance.current || !mapReady) return;
    const map = mapInstance.current;
    const source = map.getSource("tracker-points") as maplibregl.GeoJSONSource | undefined;
    if (!source) return;
    source.setData(trackerGeojson);
  }, [trackerGeojson, mapReady]);

  useEffect(() => {
    if (!leafletLayer.current || !leafletMap.current) return;
    const layer = leafletLayer.current;
    layer.clearLayers();
    const points = filteredPoints.filter(
      (point) => Number.isFinite(point.lat) && Number.isFinite(point.lon)
    );
    points.slice(0, 200).forEach((point) => {
      const color = point.kind === "ship" ? "#8892a0" : "#48f1a6";
      L.circleMarker([point.lat as number, point.lon as number], {
        radius: 4,
        color,
        weight: 1,
        opacity: 0.9,
        fillColor: color,
        fillOpacity: 0.6
      }).addTo(layer);
    });
    if (points.length) {
      const bounds = L.latLngBounds(
        points.map((point) => [point.lat as number, point.lon as number])
      );
      leafletMap.current.fitBounds(bounds, { padding: [30, 30], maxZoom: 5 });
    }
  }, [filteredPoints]);

  useEffect(() => {
    if (!leafletMap.current || !mapOpen) return;
    const map = leafletMap.current;
    const timeout = window.setTimeout(() => {
      map.invalidateSize();
    }, 150);
    return () => window.clearTimeout(timeout);
  }, [mapOpen]);

  useEffect(() => {
    if (!mapInstance.current || !mapReady) return;
    const map = mapInstance.current;
    if (!map.getSource("history-line")) return;
    const coords = (history?.history || []).map((point) => [point.lon, point.lat]);
    const feature = {
      type: "Feature",
      geometry: { type: "LineString", coordinates: coords },
      properties: {}
    };
    const source = map.getSource("history-line") as maplibregl.GeoJSONSource;
    source.setData(feature);
    if (coords.length >= 2) {
      const bounds = coords.reduce(
        (box, coord) => box.extend(coord as [number, number]),
        new maplibregl.LngLatBounds(coords[0] as [number, number], coords[0] as [number, number])
      );
      map.fitBounds(bounds, { padding: 80, maxZoom: 6 });
    }
  }, [history, mapReady]);

  useEffect(() => {
    if (!mapInstance.current || !mapReady || !mapOpen) return;
    const map = mapInstance.current;
    const timeout = window.setTimeout(() => map.resize(), 150);
    return () => window.clearTimeout(timeout);
  }, [mapOpen, mapReady]);

  return (
    <Card className="rounded-2xl p-5">
      <SectionHeader
        label="TRACKERS"
        title="Live Trackers"
        right={data ? `${data.count} signals` : "Loading"}
      />
      <div className="mt-4">
        <ErrorBanner messages={errorMessages} onRetry={refreshPoll} />
      </div>
      <div className="mt-6 space-y-4 text-sm text-slate-300">
        <Collapsible
          title="Global Risk Signals"
          meta={data ? `${riskTotals.counts.flights + riskTotals.counts.ships} active entities` : "Loading"}
          open={riskOpen}
          onToggle={() => setRiskOpen((prev) => !prev)}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            <KpiCard label="Active Flights" value={`${riskTotals.counts.flights}`} tone="text-emerald-300" />
            <KpiCard label="Active Ships" value={`${riskTotals.counts.ships}`} tone="text-slate-200" />
            <KpiCard label="Signal Density" value={`${points.length}`} tone="text-slate-200" />
          </div>
          <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="rounded-xl border border-slate-800/60 p-4">
              <p className="text-xs text-slate-400 mb-2">Dominant Categories</p>
              <div className="space-y-2">
                {riskTotals.topCategories.length ? (
                  riskTotals.topCategories.map(([category, count]) => (
                    <div key={category} className="flex items-center justify-between">
                      <span className="text-slate-200">{category}</span>
                      <span className="text-emerald-300">{count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-500">No active categories yet.</p>
                )}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800/60 p-4">
              <p className="text-xs text-slate-400 mb-2">System Status</p>
              <p className="text-sm text-emerald-300">
                {connected ? "Live stream connected" : "Streaming offline - polling snapshots"}
              </p>
              {(data?.warnings || []).length > 0 ? (
                <div className="mt-3 space-y-1 text-xs text-amber-300">
                  {data?.warnings?.map((warn) => (
                    <p key={warn}>{warn}</p>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 mt-2">No feed warnings detected.</p>
              )}
            </div>
          </div>
        </Collapsible>

        <Collapsible
          title="Tracker Map"
          meta={mapReady ? "Map online" : "Initializing"}
          open={mapOpen}
          onToggle={() => setMapOpen((prev) => !prev)}
        >
          <div
            ref={mapRef}
            className="relative h-[420px] overflow-hidden rounded-2xl border border-slate-800/60 bg-ink-950/60 scanline"
          >
            {!mapReady && !mapError ? (
              <div className="absolute inset-0 z-10 flex items-center justify-center text-xs text-slate-400 bg-ink-950/60">
                Loading map feed...
              </div>
            ) : null}
            {mapError ? (
              <div className="absolute inset-0 z-10 flex items-center justify-center text-xs text-amber-300 bg-ink-950/60">
                {mapError}
              </div>
            ) : null}
            <div className="absolute bottom-3 left-3 z-10 rounded-lg border border-emerald-400/20 bg-ink-950/80 px-3 py-2 text-xs text-emerald-300">
              {filteredPoints.length ? `${filteredPoints.length} live entities` : "Awaiting live feed"}
            </div>
            <div className="absolute bottom-3 right-3 z-10 rounded-lg border border-slate-800/60 bg-ink-950/80 px-3 py-2 text-[11px] text-slate-400">
              <p>{mapStatus}</p>
              {mapDiagnostics.length ? (
                <div className="mt-1 space-y-0.5">
                  {mapDiagnostics.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
          <div className="mt-4 rounded-2xl border border-slate-800/60 bg-ink-950/40 p-4">
            <p className="text-xs text-slate-400 mb-3">Leaflet Debug Map</p>
            <div className="relative h-[260px] overflow-hidden rounded-xl border border-slate-800/60">
              <div ref={leafletRef} className="absolute inset-0" />
              <div className="absolute bottom-2 right-2 rounded-lg border border-slate-800/60 bg-ink-950/80 px-2 py-1 text-[11px] text-slate-400">
                {leafletStatus}
              </div>
            </div>
          </div>
        </Collapsible>

        <Collapsible
          title="Live Tracker Feed"
          meta={data ? `${data.count} live signals` : "Loading"}
          open={feedOpen}
          onToggle={() => setFeedOpen((prev) => !prev)}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div>
                <label htmlFor="tracker-mode" className="text-xs text-slate-400">
                  Mode
                </label>
                <select
                  id="tracker-mode"
                  name="tracker-mode"
                  value={mode}
                  onChange={(event) => setMode(event.target.value as typeof mode)}
                  className="mt-1 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                >
                  <option value="combined">Combined</option>
                  <option value="flights">Flights</option>
                  <option value="ships">Ships</option>
                </select>
              </div>
              <div>
                <label htmlFor="tracker-category" className="text-xs text-slate-400">
                  Category
                </label>
                <select
                  id="tracker-category"
                  name="tracker-category"
                  value={categoryFilter}
                  onChange={(event) => setCategoryFilter(event.target.value)}
                  className="mt-1 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                >
                  {categories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setIncludeCommercial((prev) => !prev)}
                  className={`rounded-xl border px-3 py-2 text-xs ${
                    includeCommercial
                      ? "border-emerald-400/70 text-emerald-200"
                      : "border-slate-800/60 text-slate-400"
                  }`}
                >
                  Commercial {includeCommercial ? "On" : "Off"}
                </button>
                <button
                  type="button"
                  onClick={() => setIncludePrivate((prev) => !prev)}
                  className={`rounded-xl border px-3 py-2 text-xs ${
                    includePrivate
                      ? "border-emerald-400/70 text-emerald-200"
                      : "border-slate-800/60 text-slate-400"
                  }`}
                >
                  Private {includePrivate ? "On" : "Off"}
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div>
                <label htmlFor="tracker-country" className="text-xs text-slate-400">
                  Country
                </label>
                <input
                  id="tracker-country"
                  name="tracker-country"
                  value={countryFilter}
                  onChange={(event) => setCountryFilter(event.target.value)}
                  className="mt-1 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                  placeholder="United States"
                />
              </div>
              <div>
                <label htmlFor="tracker-operator" className="text-xs text-slate-400">
                  Operator
                </label>
                <input
                  id="tracker-operator"
                  name="tracker-operator"
                  value={operatorFilter}
                  onChange={(event) => setOperatorFilter(event.target.value)}
                  className="mt-1 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                  placeholder="AAL / American"
                />
              </div>
              <div>
                <label htmlFor="tracker-id" className="text-xs text-slate-400">
                  Identifier
                </label>
                <input
                  id="tracker-id"
                  name="tracker-id"
                  value={idFilter}
                  onChange={(event) => setIdFilter(event.target.value)}
                  className="mt-1 w-full rounded-xl bg-ink-950/60 border border-slate-800 px-3 py-2 text-sm text-slate-200"
                  placeholder="Flight / tail / ICAO24"
                />
              </div>
            </div>
            <label htmlFor="tracker-search" className="sr-only">
              Search trackers
            </label>
            <input
              id="tracker-search"
              name="tracker-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full rounded-xl bg-ink-950/60 border border-slate-800 px-4 py-2 text-sm text-slate-200"
              placeholder="Search flight number, operator, tail, ICAO24..."
            />
            {query.trim().length > 1 && (
              <div className="rounded-xl border border-slate-800/60 p-4 space-y-4">
                <p className="text-xs text-slate-400 mb-2">
                  Search Results {filteredSearchResults ? `(${filteredSearchResults.count})` : "(...)"}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {(filteredSearchResults?.points || []).map((point) => (
                    <button
                      key={point.id}
                      onClick={() => setSelectedId(point.id)}
                      className="rounded-lg border border-slate-800/60 p-3 text-left hover:border-emerald-400/40"
                    >
                      <p className="text-slate-100 font-medium">{point.label}</p>
                      <p className="text-xs text-slate-400">
                        {point.kind.toUpperCase()} • {point.category} • {point.operator_name || point.operator || "-"}
                      </p>
                    </button>
                  ))}
                </div>
                {history && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    <div className="text-xs text-slate-400 space-y-2">
                      <p>History points: {history.summary?.points ?? history.history.length}</p>
                      {history.summary?.distance_km ? (
                        <p>Route distance: {history.summary.distance_km.toFixed(2)} km</p>
                      ) : null}
                      {history.summary?.direction ? (
                        <p>
                          Direction: {history.summary.direction}{" "}
                          {history.summary.bearing_deg !== undefined ? `(${history.summary.bearing_deg.toFixed(1)}°)` : ""}
                        </p>
                      ) : null}
                      {history.summary?.avg_speed_kts ? (
                        <p>Avg speed: {history.summary.avg_speed_kts.toFixed(1)} kts</p>
                      ) : null}
                      {history.summary?.avg_altitude_ft ? (
                        <p>Avg altitude: {history.summary.avg_altitude_ft.toFixed(0)} ft</p>
                      ) : null}
                      {history.summary?.duration_sec ? (
                        <p>Duration: {(history.summary.duration_sec / 60).toFixed(1)} min</p>
                      ) : null}
                      {history.summary?.route_hint ? <p>Route: {history.summary.route_hint}</p> : null}
                    </div>
                    <div className="text-xs text-slate-400 space-y-2">
                      {detail?.point && (
                        <div className="rounded-lg border border-slate-800/60 p-3 text-xs text-slate-300 space-y-1">
                          <p className="text-slate-100 font-medium">{detail.point.label}</p>
                          <p>{detail.point.operator_name || detail.point.operator || "-"} {detail.point.flight_number || ""}</p>
                          <p>ICAO24: {detail.point.icao24 || "-"}</p>
                          <p>Tail: {detail.point.tail_number || "-"}</p>
                          <p>Country: {detail.point.country || "-"}</p>
                          <p>
                            Alt: {detail.point.altitude_ft ? `${detail.point.altitude_ft.toFixed(0)} ft` : "-"} | Spd:{" "}
                            {detail.point.speed_kts ? `${detail.point.speed_kts.toFixed(0)} kts` : "-"}
                          </p>
                        </div>
                      )}
                      <div className="max-h-48 overflow-y-auto pr-2 space-y-1">
                        {history.history.slice(-12).map((point) => (
                          <div key={point.ts} className="flex justify-between">
                            <span>{new Date(point.ts * 1000).toLocaleTimeString()}</span>
                            <span>
                              {point.lat.toFixed(2)}, {point.lon.toFixed(2)}{" "}
                              {point.speed_kts ? `${point.speed_kts.toFixed(0)} kts` : ""}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {filteredPoints.slice(0, 12).map((point) => (
                <div key={`${point.kind}-${point.label}`} className="rounded-xl border border-slate-800/60 p-4">
                  <p className="text-slate-100 font-medium">{point.label}</p>
                  <p className="text-xs text-slate-400">
                    {point.kind.toUpperCase()} • {point.category} • {point.country || "unknown"}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </Collapsible>
      </div>
    </Card>
  );
}
