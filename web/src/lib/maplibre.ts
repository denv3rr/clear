export type MapLibre = typeof import("maplibre-gl/dist/maplibre-gl-csp");

let cached: MapLibre | null = null;

export async function loadMapLibre(): Promise<MapLibre> {
  if (cached) return cached;
  const mod = await import("maplibre-gl/dist/maplibre-gl-csp");
  const maplibre = (mod as { default?: MapLibre }).default ?? (mod as MapLibre);
  try {
    const workerMod = await import(
      "maplibre-gl/dist/maplibre-gl-csp-worker.js?worker&inline"
    );
    const workerClass =
      (workerMod as { default?: typeof Worker }).default ??
      (workerMod as typeof Worker);
    if (workerClass) {
      maplibre.workerClass = workerClass;
    }
  } catch {
    const workerUrl = new URL(
      "maplibre-gl/dist/maplibre-gl-csp-worker.js",
      import.meta.url
    );
    maplibre.workerClass = class extends Worker {
      constructor() {
        super(workerUrl);
      }
    };
  }
  cached = maplibre;
  return maplibre;
}
