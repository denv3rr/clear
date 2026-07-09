export type MapLibre = typeof import("maplibre-gl/dist/maplibre-gl-csp");

import mapLibreCssUrl from "maplibre-gl/dist/maplibre-gl.css?url";
import workerUrl from "maplibre-gl/dist/maplibre-gl-csp-worker.js?url";

export const mapLibreWorkerUrl = workerUrl;

let cached: MapLibre | null = null;

function ensureMapLibreStylesheet() {
  if (typeof document === "undefined") return;
  if (document.querySelector("link[data-clear-maplibre-css]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = mapLibreCssUrl;
  link.dataset.clearMaplibreCss = "true";
  document.head.appendChild(link);
}

export async function loadMapLibre(): Promise<MapLibre> {
  if (cached) return cached;
  ensureMapLibreStylesheet();
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
