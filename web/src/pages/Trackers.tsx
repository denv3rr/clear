import { useEffect, useMemo, useRef, useState } from "react";
import { Card } from "../components/ui/Card";
import { SectionHeader } from "../components/ui/SectionHeader";
import { apiGet, useApi } from "../lib/api";
import { useTrackerStream } from "../lib/stream";
import maplibregl from "maplibre-gl";

type TrackerSnapshot = {
  count: number;
  warnings: string[];
  points: { kind: string; label: string; category: string }[];
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
  const { data: streamData } = useTrackerStream<TrackerSnapshot>({ interval: 5, mode: "combined" });
  const { data: pollData } = useApi<TrackerSnapshot>("/api/trackers/snapshot?mode=combined", { interval: 20000 });
  const data = streamData || pollData;
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TrackerDetail | null>(null);
  const history = detail ? { id: detail.id, history: detail.history, summary: detail.summary } : null;
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapInstance = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  const searchPath = useMemo(() => `/api/trackers/search?q=${encodeURIComponent(query)}&limit=12`, [query]);
  const { data: searchResults } = useApi<SearchResult>(searchPath, {
    enabled: query.trim().length > 1
  });

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    apiGet<TrackerDetail>(`/api/trackers/detail/${encodeURIComponent(selectedId)}`, 0)
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [selectedId]);

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;
    const map = new maplibregl.Map({
      container: mapRef.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: [0, 15],
      zoom: 1.4,
      attributionControl: false
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("load", () => {
      setMapReady(true);
      setMapError(null);
      map.resize();
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
    });
    map.on("error", () => {
      setMapError("Map data unavailable.");
    });
    mapInstance.current = map;
    return () => map.remove();
  }, []);

  useEffect(() => {
    if (!mapInstance.current) return;
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
  }, [history]);

  return (
    <Card className="rounded-2xl p-6">
      <SectionHeader
        label="TRACKERS"
        title="Live Trackers"
        right={data ? `${data.count} signals` : "Loading"}
      />
      <div className="mt-6">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="w-full rounded-xl bg-ink-950/60 border border-slate-800 px-4 py-2 text-sm text-slate-200"
          placeholder="Search flight number, operator, tail, ICAO24..."
        />
      </div>
      <div className="mt-6 space-y-4 text-sm text-slate-300">
        {(data?.warnings || []).length > 0 && (
          <div className="text-amber-300">
            {data?.warnings?.map((warn) => (
              <p key={warn}>{warn}</p>
            ))}
          </div>
        )}
        {query.trim().length > 1 && (
          <div className="rounded-xl border border-slate-800/60 p-4 space-y-4">
            <p className="text-xs text-slate-400 mb-2">
              Search Results {searchResults ? `(${searchResults.count})` : "(...)"} 
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(searchResults?.points || []).map((point) => (
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
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-xl border border-slate-800/60 overflow-hidden relative h-56">
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(data?.points || []).slice(0, 12).map((point) => (
            <div key={`${point.kind}-${point.label}`} className="rounded-xl border border-slate-800/60 p-4">
              <p className="text-slate-100 font-medium">{point.label}</p>
              <p className="text-xs text-slate-400">{point.kind.toUpperCase()} • {point.category}</p>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
