import maplibregl from "maplibre-gl/dist/maplibre-gl-csp";
import MapLibreWorker from "maplibre-gl/dist/maplibre-gl-csp-worker?worker";

maplibregl.workerClass = MapLibreWorker;

export default maplibregl;
