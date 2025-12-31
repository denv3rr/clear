export type MapLibre = typeof import("maplibre-gl/dist/maplibre-gl-csp");

let cached: MapLibre | null = null;

export async function loadMapLibre(): Promise<MapLibre> {
  if (cached) return cached;
  const mod = await import("maplibre-gl/dist/maplibre-gl-csp");
  const maplibre = (mod as { default?: MapLibre }).default ?? (mod as MapLibre);
  const workerMod = await import(
    "maplibre-gl/dist/maplibre-gl-csp-worker?worker"
  );
  maplibre.workerClass = (workerMod as { default: new () => Worker }).default;
  cached = maplibre;
  return maplibre;
}
