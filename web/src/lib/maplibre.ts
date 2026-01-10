export type MapLibre = typeof import("maplibre-gl/dist/maplibre-gl-csp");

import workerUrl from "maplibre-gl/dist/maplibre-gl-csp-worker.js?url";

export const mapLibreWorkerUrl = workerUrl;

let cached: MapLibre | null = null;

export async function loadMapLibre(): Promise<MapLibre> {
  if (cached) return cached;
  const mod = await import("maplibre-gl/dist/maplibre-gl-csp");
  const maplibre = (mod as { default?: MapLibre }).default ?? (mod as MapLibre);
  if (workerUrl) {
    maplibre.workerClass = class extends Worker {
      constructor() {
        super(workerUrl);
      }
    };
  }
  cached = maplibre;
  return maplibre;
}
