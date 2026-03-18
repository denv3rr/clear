import { useEffect, useMemo, useRef, useState } from "react";
import type { MutableRefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import {
  Html,
  Line,
  OrbitControls,
  PerformanceMonitor,
  Stars
} from "@react-three/drei";
import type { Mesh } from "three";
import * as THREE from "three";
import { X, Orbit, RadioTower, Route, AlertTriangle } from "lucide-react";
import { apiGet, useApi } from "../../lib/api";
import {
  type IntelSceneLens,
  type SceneCameraPreset,
  type TrackerSceneMode,
  useSceneController
} from "../../lib/scene";
import { useReducedMotionPreference } from "../../lib/useReducedMotion";

type SceneFeature = {
  id: string;
  layer: string;
  geometry: {
    type: "Point" | "LineString";
    coordinates: number[] | number[][];
  };
  ts?: number | null;
  properties?: Record<string, unknown>;
  confidence?: number | null;
  freshness?: {
    age_sec?: number | null;
    state?: string | null;
    is_stale?: boolean;
  };
  warnings?: string[];
};

type SceneLayer = {
  id: string;
  kind: "point" | "path";
  label: string;
  features: SceneFeature[];
  meta?: {
    count?: number;
    warnings?: string[];
  };
};

type FocusTarget = {
  id: string;
  label?: string;
  kind?: string;
  category?: string;
  lat?: number | null;
  lon?: number | null;
  confidence?: number | null;
};

type ScenePayload = {
  scene_id: string;
  title: string;
  kind: string;
  camera_defaults?: {
    target_lat?: number;
    target_lon?: number;
    distance?: number;
  };
  timeline?: {
    mode?: string;
    point_count?: number;
    trail_count?: number;
    start_ts?: number | null;
    end_ts?: number | null;
  };
  layers: SceneLayer[];
  focus_targets: FocusTarget[];
  meta?: {
    timestamp?: number;
    available_lenses?: string[];
    warnings?: string[];
  };
};

type TrackerPresentationPresetId =
  | "operations-overview"
  | "air-picture"
  | "maritime-picture"
  | "lead-signal";

type IntelPresentationPresetId =
  | "global-risk"
  | "weather-watch"
  | "conflict-watch"
  | "news-pressure";

type PresentationPresetId = TrackerPresentationPresetId | IntelPresentationPresetId;

const TRACKER_MODE_OPTIONS: Array<{ id: TrackerSceneMode; label: string }> = [
  { id: "combined", label: "Combined" },
  { id: "flights", label: "Flights" },
  { id: "ships", label: "Ships" }
];

const INTEL_LENS_OPTIONS: Array<{ id: IntelSceneLens; label: string }> = [
  { id: "combined", label: "Combined" },
  { id: "weather", label: "Weather" },
  { id: "conflict", label: "Conflict" },
  { id: "news", label: "News" }
];

const CAMERA_PRESET_OPTIONS: Array<{ id: SceneCameraPreset; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "focus", label: "Follow Selection" }
];

const GLOBE_RADIUS = 1.6;
const SCENE_ROTATION_VALUES: [number, number, number] = [0.15, 0.3, 0];
const SCENE_ROTATION = new THREE.Euler(...SCENE_ROTATION_VALUES);
const TOUR_INTERVAL_MS = 3600;

const TRACKER_PRESENTATION_PRESETS: Array<{
  id: TrackerPresentationPresetId;
  label: string;
}> = [
  { id: "operations-overview", label: "Ops Overview" },
  { id: "air-picture", label: "Air Picture" },
  { id: "maritime-picture", label: "Sea Picture" },
  { id: "lead-signal", label: "Lead Signal" }
];

const INTEL_PRESENTATION_PRESETS: Array<{
  id: IntelPresentationPresetId;
  label: string;
}> = [
  { id: "global-risk", label: "Global Risk" },
  { id: "weather-watch", label: "Weather Watch" },
  { id: "conflict-watch", label: "Conflict Watch" },
  { id: "news-pressure", label: "News Pressure" }
];

function latLonToVector(
  lat: number,
  lon: number,
  radius = GLOBE_RADIUS,
  altitude = 0
): THREE.Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((lon + 180) * Math.PI) / 180;
  const r = radius + altitude;
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta)
  );
}

function formatTimestamp(ts?: number | null) {
  if (!ts) return "Live";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(ts * 1000));
}

function getQualityLabel(qualityFactor: number, reducedMotion: boolean) {
  if (reducedMotion) return "Reduced motion";
  if (qualityFactor < 0.58) return "Adaptive low";
  if (qualityFactor < 0.78) return "Adaptive balanced";
  return "Adaptive high";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function getNumericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function getFreshnessAge(feature: SceneFeature) {
  const age = feature.freshness?.age_sec;
  return typeof age === "number" && Number.isFinite(age) ? age : Number.MAX_SAFE_INTEGER;
}

function getFeatureConfidence(feature: SceneFeature) {
  return typeof feature.confidence === "number" && Number.isFinite(feature.confidence)
    ? feature.confidence
    : 0;
}

function getTrackerKind(feature: SceneFeature) {
  const properties = asRecord(feature.properties);
  return String(properties?.kind || "");
}

function getTrackerSpeedHeat(feature: SceneFeature) {
  return getNumericValue(asRecord(feature.properties)?.speed_heat) || 0;
}

function getFeatureNewsCount(feature: SceneFeature) {
  return getNumericValue(asRecord(asRecord(feature.properties)?.news)?.count) || 0;
}

function getLensLabel(lens: IntelSceneLens) {
  return INTEL_LENS_OPTIONS.find((option) => option.id === lens)?.label || "Combined";
}

function getFeatureLabel(feature: SceneFeature) {
  const properties = asRecord(feature.properties);
  return String(properties?.label || properties?.region || feature.id);
}

function getFeatureLensScore(feature: SceneFeature, lens: IntelSceneLens): number | null {
  const properties = asRecord(feature.properties);
  if (!properties) return null;
  if (lens === "combined") {
    return getNumericValue(asRecord(properties.combined_risk)?.score);
  }
  return getNumericValue(asRecord(properties[lens])?.score);
}

function getFeaturePresentation(feature: SceneFeature) {
  return asRecord(asRecord(feature.properties)?.presentation);
}

function getFeatureDominantChannel(feature: SceneFeature): IntelSceneLens | "combined" {
  const dominant = getFeaturePresentation(feature)?.dominant_channel;
  if (
    dominant === "weather" ||
    dominant === "conflict" ||
    dominant === "news" ||
    dominant === "combined"
  ) {
    return dominant;
  }
  return "combined";
}

function getFeatureIntensity(
  feature: SceneFeature,
  sceneId: "trackers" | "intel",
  intelLens: IntelSceneLens
) {
  const properties = asRecord(feature.properties);
  if (sceneId === "intel") {
    const score = getFeatureLensScore(feature, intelLens);
    const presentationIntensity = getNumericValue(getFeaturePresentation(feature)?.intensity);
    const rawValue = score !== null ? score / 10 : presentationIntensity;
    return Math.max(0.26, Math.min(1, rawValue ?? 0.58));
  }
  const speedHeat = getNumericValue(properties?.speed_heat);
  return Math.max(0.25, Math.min(1, speedHeat ?? 0.55));
}

function getFeatureAccent(
  feature: SceneFeature,
  sceneId: "trackers" | "intel",
  intelLens: IntelSceneLens
) {
  const properties = asRecord(feature.properties);
  if (sceneId === "intel") {
    const channel = intelLens === "combined" ? getFeatureDominantChannel(feature) : intelLens;
    if (channel === "weather") return "#75d7ff";
    if (channel === "conflict") return "#ff8b73";
    if (channel === "news") return "#ffd166";
    const riskScore = getFeatureLensScore(feature, "combined") ?? 0;
    return riskScore >= 7 ? "#ff9e73" : "#48f1a6";
  }
  return properties?.kind === "ship" ? "#7dffd3" : "#d2ffef";
}

function getFeatureTooltipCopy(
  feature: SceneFeature,
  sceneId: "trackers" | "intel",
  intelLens: IntelSceneLens
) {
  const properties = asRecord(feature.properties);
  if (sceneId === "intel") {
    const combinedRisk = asRecord(properties?.combined_risk);
    const level = String(combinedRisk?.level || "Unknown");
    const lensLabel = getLensLabel(intelLens);
    const lensScore = getFeatureLensScore(feature, intelLens);
    const dominant = getFeatureDominantChannel(feature);
    const activeLabel = intelLens === "combined" ? dominant : intelLens;
    return `${lensLabel} ${lensScore !== null ? `${Math.round(lensScore)}/10` : "n/a"} • ${level} • ${String(activeLabel).toUpperCase()}`;
  }
  return `${String(properties?.kind || "signal").toUpperCase()} • ${String(properties?.category || "unknown")}`;
}

function getSelectedIntelCopy(feature: SceneFeature | null, intelLens: IntelSceneLens) {
  if (!feature) return "Choose a region to inspect the fused signal layers.";
  const properties = asRecord(feature.properties);
  const combinedRisk = asRecord(properties?.combined_risk);
  const news = asRecord(properties?.news);
  const topSignal = String(getFeaturePresentation(feature)?.top_signal || "Regional monitoring active.");
  const newsCount = Math.round(getNumericValue(news?.count) || 0);
  const level = String(combinedRisk?.level || "Unknown");
  const lensLabel = getLensLabel(intelLens);
  const lensScore = getFeatureLensScore(feature, intelLens);
  return `${lensLabel} ${lensScore !== null ? `${Math.round(lensScore)}/10` : "n/a"} • ${level} • ${newsCount} headlines. ${topSignal}`;
}

function rankTrackerFeatures(
  features: SceneFeature[],
  mode: TrackerSceneMode
) {
  const filtered =
    mode === "combined"
      ? features
      : features.filter((feature) =>
          mode === "flights"
            ? getTrackerKind(feature) === "flight"
            : getTrackerKind(feature) === "ship"
        );
  return [...filtered].sort((left, right) => {
    const freshnessDelta = getFreshnessAge(left) - getFreshnessAge(right);
    if (freshnessDelta !== 0) return freshnessDelta;
    const confidenceDelta = getFeatureConfidence(right) - getFeatureConfidence(left);
    if (confidenceDelta !== 0) return confidenceDelta;
    return getTrackerSpeedHeat(right) - getTrackerSpeedHeat(left);
  });
}

function rankIntelFeatures(
  features: SceneFeature[],
  lens: IntelSceneLens
) {
  return [...features].sort((left, right) => {
    const scoreDelta = (getFeatureLensScore(right, lens) || 0) - (getFeatureLensScore(left, lens) || 0);
    if (scoreDelta !== 0) return scoreDelta;
    const newsDelta = getFeatureNewsCount(right) - getFeatureNewsCount(left);
    if (newsDelta !== 0) return newsDelta;
    return getFeatureConfidence(right) - getFeatureConfidence(left);
  });
}

function getFocusOrder(
  sceneId: "trackers" | "intel",
  features: SceneFeature[],
  trackerMode: TrackerSceneMode,
  intelLens: IntelSceneLens
) {
  return sceneId === "intel"
    ? rankIntelFeatures(features, intelLens)
    : rankTrackerFeatures(features, trackerMode);
}

function getDerivedPresetId(
  sceneId: "trackers" | "intel",
  sceneState: { cameraPreset: SceneCameraPreset; trackerMode: TrackerSceneMode; intelLens: IntelSceneLens }
): PresentationPresetId {
  if (sceneId === "intel") {
    if (sceneState.intelLens === "weather") return "weather-watch";
    if (sceneState.intelLens === "conflict") return "conflict-watch";
    if (sceneState.intelLens === "news") return "news-pressure";
    return "global-risk";
  }
  if (sceneState.cameraPreset === "focus") return "lead-signal";
  if (sceneState.trackerMode === "flights") return "air-picture";
  if (sceneState.trackerMode === "ships") return "maritime-picture";
  return "operations-overview";
}

function getFocusTargetMeta(
  sceneId: "trackers" | "intel",
  target: FocusTarget
) {
  if (sceneId === "intel") {
    return `${String(target.kind || "combined").toUpperCase()} • ${target.category || "Unknown"}`;
  }
  return `${String(target.kind || "signal").toUpperCase()} • ${target.category || "unknown"}`;
}

async function buildFallbackTrackerScene(mode: TrackerSceneMode): Promise<ScenePayload> {
  const snapshot = await apiGet<{
    mode?: string;
    count: number;
    warnings?: string[];
    points: Array<{
      id?: string;
      label?: string;
      kind?: string;
      category?: string;
      lat?: number;
      lon?: number;
      updated_ts?: number | null;
      speed_heat?: number | null;
      speed_kts?: number | null;
      operator?: string | null;
      operator_name?: string | null;
      country?: string | null;
    }>;
  }>(`/api/trackers/snapshot?mode=${mode}`);
  return {
    scene_id: "osint-trackers-fallback",
    title: "OSINT Tracker Scene",
    kind: "osint",
    camera_defaults: {
      target_lat: 12,
      target_lon: 8,
      distance: 3.4
    },
    timeline: {
      mode: snapshot.mode || mode,
      point_count: snapshot.count || snapshot.points.length,
      trail_count: 0
    },
    layers: [
      {
        id: "live-trackers",
        kind: "point",
        label: "Live Trackers",
        features: snapshot.points
          .filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lon))
          .slice(0, 18)
          .map((point, index) => ({
            id: point.id || `fallback-${index}`,
            layer: "live-trackers",
            geometry: {
              type: "Point" as const,
              coordinates: [point.lon as number, point.lat as number]
            },
            ts: point.updated_ts || null,
            properties: {
              label: point.label,
              kind: point.kind,
              category: point.category,
              operator: point.operator,
              operator_name: point.operator_name,
              country: point.country,
              speed_kts: point.speed_kts,
              speed_heat: point.speed_heat
            },
            confidence: null,
            freshness: {
              state: "fallback",
              age_sec: null,
              is_stale: false
            }
          })),
        meta: {
          count: snapshot.points.length,
          warnings: [
            "Scene route unavailable; using tracker snapshot fallback.",
            ...(snapshot.warnings || [])
          ]
        }
      },
      {
        id: "tracker-trails",
        kind: "path",
        label: "Tracker Trails",
        features: [],
        meta: {
          count: 0,
          warnings: ["Replay trails unavailable in fallback mode."]
        }
      }
    ],
    focus_targets: snapshot.points
      .filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lon))
      .slice(0, 6)
      .map((point, index) => ({
        id: point.id || `fallback-${index}`,
        label: point.label,
        kind: point.kind,
        category: point.category,
        lat: point.lat,
        lon: point.lon,
        confidence: null
      })),
    meta: {
      timestamp: Math.floor(Date.now() / 1000),
      warnings: [
        "Scene route unavailable; using tracker snapshot fallback.",
        ...(snapshot.warnings || [])
      ]
    }
  };
}

function AdaptiveDprController({
  qualityFactor,
  reducedMotion
}: {
  qualityFactor: number;
  reducedMotion: boolean;
}) {
  const setDpr = useThree((state) => state.setDpr);
  const initialDpr = useThree((state) => state.viewport.initialDpr);

  useEffect(() => {
    const baseDpr = Math.min(initialDpr || 1, 1.6);
    const nextDpr = reducedMotion
      ? 1
      : Math.max(0.85, Math.min(1.55, baseDpr * (0.72 + qualityFactor * 0.4)));
    setDpr(Number(nextDpr.toFixed(2)));
  }, [initialDpr, qualityFactor, reducedMotion, setDpr]);

  return null;
}

function CameraRig({
  cameraPreset,
  controlsRef,
  defaults,
  focusTarget,
  reducedMotion
}: {
  cameraPreset: SceneCameraPreset;
  controlsRef: MutableRefObject<any>;
  defaults?: ScenePayload["camera_defaults"];
  focusTarget: FocusTarget | null;
  reducedMotion: boolean;
}) {
  const { camera } = useThree();
  const isFocusPreset =
    cameraPreset === "focus" &&
    Number.isFinite(focusTarget?.lat) &&
    Number.isFinite(focusTarget?.lon);

  const targetVector = useMemo(() => {
    const lat = isFocusPreset
      ? Number(focusTarget?.lat)
      : Number(defaults?.target_lat ?? 0);
    const lon = isFocusPreset
      ? Number(focusTarget?.lon)
      : Number(defaults?.target_lon ?? 0);
    return latLonToVector(lat, lon, GLOBE_RADIUS, 0.02).applyEuler(SCENE_ROTATION);
  }, [
    defaults?.target_lat,
    defaults?.target_lon,
    focusTarget?.lat,
    focusTarget?.lon,
    isFocusPreset
  ]);

  const cameraVector = useMemo(() => {
    const baseDistance = Math.max(2.6, Number(defaults?.distance ?? 3.35));
    const distance = isFocusPreset
      ? Math.max(2.45, baseDistance - 0.35)
      : Math.max(2.8, baseDistance);
    return targetVector.clone().normalize().multiplyScalar(distance);
  }, [defaults?.distance, isFocusPreset, targetVector]);

  useEffect(() => {
    if (!reducedMotion) return;
    camera.position.copy(cameraVector);
    const controls = controlsRef.current;
    if (controls?.target) {
      controls.target.copy(targetVector.clone().multiplyScalar(0.45));
      controls.update();
      return;
    }
    camera.lookAt(targetVector);
  }, [camera, cameraVector, controlsRef, reducedMotion, targetVector]);

  useFrame(() => {
    if (reducedMotion) return;
    camera.position.lerp(cameraVector, 0.075);
    const controls = controlsRef.current;
    if (controls?.target) {
      const target = targetVector.clone().multiplyScalar(0.45);
      controls.target.lerp(target, 0.12);
      controls.update();
    } else {
      camera.lookAt(targetVector);
    }
  });

  return null;
}

function GlobeShell({
  qualityFactor,
  reducedMotion
}: {
  qualityFactor: number;
  reducedMotion: boolean;
}) {
  const atmosphereRef = useRef<Mesh | null>(null);
  const edgeGeometry = useMemo(
    () => new THREE.SphereGeometry(GLOBE_RADIUS, reducedMotion ? 16 : 24, reducedMotion ? 16 : 24),
    [reducedMotion]
  );
  const shellSegments = reducedMotion ? 42 : 64;
  const atmosphereOpacity = reducedMotion ? 0.05 : 0.05 + qualityFactor * 0.05;

  useFrame((state) => {
    if (!reducedMotion && atmosphereRef.current) {
      atmosphereRef.current.rotation.y = state.clock.elapsedTime * 0.03;
    }
  });

  return (
    <group>
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS, shellSegments, shellSegments]} />
        <meshStandardMaterial
          color="#05111a"
          emissive="#0e513c"
          emissiveIntensity={0.45 + qualityFactor * 0.25}
          roughness={0.82}
          metalness={0.12}
          transparent
          opacity={0.9}
        />
      </mesh>
      <mesh ref={atmosphereRef} scale={1.07}>
        <sphereGeometry args={[GLOBE_RADIUS, shellSegments, shellSegments]} />
        <meshBasicMaterial
          color="#48f1a6"
          transparent
          opacity={atmosphereOpacity}
          side={THREE.BackSide}
        />
      </mesh>
      <lineSegments>
        <edgesGeometry args={[edgeGeometry]} />
        <lineBasicMaterial color="#48f1a6" transparent opacity={reducedMotion ? 0.08 : 0.12} />
      </lineSegments>
    </group>
  );
}

function TrackerTrail({
  active,
  feature
}: {
  active: boolean;
  feature: SceneFeature;
}) {
  const coordinates = Array.isArray(feature.geometry.coordinates)
    ? (feature.geometry.coordinates as number[][])
    : [];
  const points = useMemo(
    () =>
      coordinates
        .filter((coord) => Array.isArray(coord) && coord.length >= 2)
        .map((coord) => latLonToVector(coord[1], coord[0], GLOBE_RADIUS, 0.03)),
    [coordinates]
  );

  if (points.length < 2) return null;

  return (
    <Line
      points={points}
      color={active ? "#9cffdb" : "#48f1a6"}
      lineWidth={active ? 2.2 : 1.2}
      transparent
      opacity={active ? 0.95 : 0.5}
    />
  );
}

function LivePoint({
  accentColor,
  feature,
  intensity,
  intelLens,
  onSelect,
  reducedMotion,
  sceneId,
  selected
}: {
  accentColor: string;
  feature: SceneFeature;
  intensity: number;
  intelLens: IntelSceneLens;
  onSelect: (id: string) => void;
  reducedMotion: boolean;
  sceneId: "trackers" | "intel";
  selected: boolean;
}) {
  const markerRef = useRef<Mesh | null>(null);
  const haloRef = useRef<Mesh | null>(null);
  const properties = asRecord(feature.properties) || {};
  const coords = Array.isArray(feature.geometry.coordinates)
    ? (feature.geometry.coordinates as number[])
    : [];
  const position = useMemo(() => {
    if (coords.length < 2) {
      return new THREE.Vector3(0, 0, 0);
    }
    return latLonToVector(coords[1], coords[0], GLOBE_RADIUS, 0.045);
  }, [coords]);
  const pulseOffset = useMemo(() => feature.id.length * 0.17, [feature.id]);

  useEffect(() => {
    if (!reducedMotion) return;
    markerRef.current?.scale.setScalar(selected ? 1.08 + intensity * 0.28 : 0.92 + intensity * 0.18);
    haloRef.current?.scale.setScalar(selected ? 1.28 + intensity * 0.24 : 1.02 + intensity * 0.18);
  }, [intensity, reducedMotion, selected]);

  useFrame((state) => {
    if (reducedMotion) return;
    const pulse = 1 + Math.sin(state.clock.elapsedTime * 2.8 + pulseOffset) * 0.14;
    if (markerRef.current) {
      const baseScale = selected ? 1.04 + intensity * 0.32 : 0.88 + intensity * 0.24;
      markerRef.current.scale.setScalar(pulse * baseScale);
    }
    if (haloRef.current) {
      haloRef.current.scale.setScalar(selected ? 1.18 + intensity * 0.42 : 0.96 + intensity * 0.3);
    }
  });

  return (
    <group
      position={position}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(feature.id);
      }}
    >
      <mesh ref={haloRef}>
        <sphereGeometry args={[selected ? 0.05 + intensity * 0.02 : 0.034 + intensity * 0.014, 18, 18]} />
        <meshBasicMaterial color={accentColor} transparent opacity={selected ? 0.28 : 0.15} />
      </mesh>
      <mesh ref={markerRef}>
        <sphereGeometry args={[selected ? 0.025 + intensity * 0.012 : 0.02 + intensity * 0.008, 18, 18]} />
        <meshStandardMaterial
          color={accentColor}
          emissive={accentColor}
          emissiveIntensity={selected ? 1.7 : 1.2}
        />
      </mesh>
      {selected ? (
        <Html distanceFactor={14}>
          <div className="globe-tooltip">
            <p className="globe-tooltip-title">
              {getFeatureLabel(feature)}
            </p>
            <p className="globe-tooltip-copy">
              {getFeatureTooltipCopy(
                feature,
                sceneId,
                intelLens
              )}
            </p>
          </div>
        </Html>
      ) : null}
    </group>
  );
}

function GlobeScene({
  cameraPreset,
  intelLens,
  onQualityChange,
  onSelect,
  qualityFactor,
  reducedMotion,
  scene,
  sceneId,
  selectedFocus,
  selectedId
}: {
  cameraPreset: SceneCameraPreset;
  intelLens: IntelSceneLens;
  onQualityChange: (factor: number) => void;
  onSelect: (id: string) => void;
  qualityFactor: number;
  reducedMotion: boolean;
  scene: ScenePayload;
  sceneId: "trackers" | "intel";
  selectedFocus: FocusTarget | null;
  selectedId: string | null;
}) {
  const controlsRef = useRef<any>(null);
  const pointLayer = scene.layers.find((layer) => layer.kind === "point");
  const pathLayer = scene.layers.find((layer) => layer.kind === "path");
  const liveFeatures = pointLayer?.features || [];
  const pathFeatures = pathLayer?.features || [];
  const activeQuality = reducedMotion ? 0.5 : qualityFactor;
  const starsCount = reducedMotion ? 450 : Math.round(1200 + activeQuality * 2200);
  const bloomIntensity = reducedMotion ? 0.25 : 0.35 + activeQuality * 0.55;

  return (
    <Canvas
      camera={{ position: [0, 0, 4.2], fov: 42 }}
      dpr={reducedMotion ? 1 : [1, 1.6]}
      performance={{ min: 0.55, debounce: 300 }}
    >
      <AdaptiveDprController qualityFactor={activeQuality} reducedMotion={reducedMotion} />
      {!reducedMotion ? (
        <PerformanceMonitor
          bounds={(refreshrate) => (refreshrate > 100 ? [55, 100] : [40, 58])}
          onChange={({ factor }) => onQualityChange(Math.max(0.4, factor))}
          onFallback={() => onQualityChange(0.38)}
        />
      ) : null}
      <color attach="background" args={["#02060b"]} />
      <fog attach="fog" args={["#02060b", 4.2, 8]} />
      <ambientLight intensity={0.42} />
      <directionalLight
        position={[4, 3, 5]}
        intensity={0.85 + activeQuality * 0.55}
        color="#c8fff0"
      />
      <pointLight
        position={[-3, 2, -4]}
        intensity={reducedMotion ? 0.45 : 0.45 + activeQuality * 0.4}
        color="#48f1a6"
      />
      <Stars
        radius={80}
        depth={40}
        count={starsCount}
        factor={reducedMotion ? 1.3 : 3.2}
        saturation={0}
        fade
        speed={reducedMotion ? 0 : 0.55}
      />
      <CameraRig
        cameraPreset={cameraPreset}
        focusTarget={selectedFocus}
        defaults={scene.camera_defaults}
        controlsRef={controlsRef}
        reducedMotion={reducedMotion}
      />
      <group rotation={SCENE_ROTATION_VALUES}>
        <GlobeShell qualityFactor={activeQuality} reducedMotion={reducedMotion} />
        <group>
          {pathFeatures.map((feature) => {
            const trackerId = String(feature.properties?.tracker_id || "");
            return (
              <TrackerTrail
                key={feature.id}
                feature={feature}
                active={Boolean(selectedId && trackerId === selectedId)}
              />
            );
          })}
        </group>
        <group>
          {liveFeatures.map((feature) => (
            <LivePoint
              key={feature.id}
              accentColor={getFeatureAccent(feature, sceneId, intelLens)}
              feature={feature}
              intensity={getFeatureIntensity(feature, sceneId, intelLens)}
              intelLens={intelLens}
              selected={feature.id === selectedId}
              reducedMotion={reducedMotion}
              sceneId={sceneId}
              onSelect={onSelect}
            />
          ))}
        </group>
      </group>
      <OrbitControls
        ref={controlsRef}
        enablePan={false}
        enableDamping={!reducedMotion}
        dampingFactor={0.08}
        autoRotate={!reducedMotion && cameraPreset === "overview"}
        autoRotateSpeed={0.35}
        minDistance={2.35}
        maxDistance={6.5}
      />
      <EffectComposer multisampling={0}>
        <Bloom intensity={bloomIntensity} luminanceThreshold={0.16} mipmapBlur />
      </EffectComposer>
    </Canvas>
  );
}

export function GlobeOverlay() {
  const {
    activeScene,
    activeScenePath,
    closeScene,
    isOpen,
    sceneState,
    setCameraPreset,
    setIntelLens,
    setTrackerMode
  } = useSceneController();
  const reducedMotion = useReducedMotionPreference();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [fallbackScene, setFallbackScene] = useState<ScenePayload | null>(null);
  const [fallbackError, setFallbackError] = useState<string | null>(null);
  const [qualityFactor, setQualityFactor] = useState(reducedMotion ? 0.5 : 0.82);
  const sceneId = activeScene?.id || "trackers";
  const hasTrackerFallback = activeScene?.fallbackStrategy === "trackerSnapshot";
  const { data, error, loading, refresh } = useApi<ScenePayload>(
    activeScenePath || "/api/osint/scene/trackers?mode=combined",
    {
      enabled: isOpen && Boolean(activeScene),
      interval: isOpen ? (sceneId === "intel" ? 120000 : 30000) : 0
    }
  );

  useEffect(() => {
    setQualityFactor(reducedMotion ? 0.5 : 0.82);
  }, [reducedMotion]);

  useEffect(() => {
    if (!isOpen) {
      setFallbackScene(null);
      setFallbackError(null);
      setSelectedId(null);
      return;
    }
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [isOpen]);

  useEffect(() => {
    setFallbackScene(null);
    setFallbackError(null);
    setSelectedId(null);
  }, [activeScene?.id]);

  useEffect(() => {
    if (!isOpen || !error || !activeScene || data || !hasTrackerFallback) return;
    let mounted = true;
    buildFallbackTrackerScene(sceneState.trackerMode)
      .then((scene) => {
        if (mounted) {
          setFallbackScene(scene);
          setFallbackError(null);
        }
      })
      .catch((sceneErr) => {
        if (mounted) {
          setFallbackScene(null);
          setFallbackError(
            sceneErr instanceof Error ? sceneErr.message : "Fallback scene unavailable."
          );
        }
      });
    return () => {
      mounted = false;
    };
  }, [activeScene, data, error, hasTrackerFallback, isOpen, sceneState.trackerMode]);

  useEffect(() => {
    if (!data) return;
    setFallbackScene(null);
    setFallbackError(null);
  }, [data]);

  const scene = data || fallbackScene;
  const pointLayer = scene?.layers.find((layer) => layer.kind === "point");
  const pathLayer = scene?.layers.find((layer) => layer.kind === "path");
  const pointFeatures = pointLayer?.features || [];
  const warnings = Array.from(
    new Set([
      ...(error ? [error] : []),
      ...(fallbackError ? [fallbackError] : []),
      ...((scene?.meta?.warnings || []) as string[])
    ])
  );
  const sceneUnavailable = !scene && !loading && Boolean(error || fallbackError);

  useEffect(() => {
    if (!scene?.focus_targets?.length) {
      setSelectedId(null);
      return;
    }
    if (selectedId && scene.focus_targets.some((target) => target.id === selectedId)) {
      return;
    }
    setSelectedId(scene.focus_targets[0]?.id || null);
  }, [scene, selectedId]);

  const selectedFocus = useMemo(
    () =>
      scene?.focus_targets.find((target) => target.id === selectedId) ||
      scene?.focus_targets[0] ||
      null,
    [scene, selectedId]
  );
  const selectedFeature = useMemo(
    () =>
      pointFeatures.find((feature) => feature.id === selectedId) ||
      pointFeatures[0] ||
      null,
    [pointFeatures, selectedId]
  );
  const intelHighRiskCount = useMemo(
    () =>
      pointFeatures.filter((feature) => {
        const score = getFeatureLensScore(feature, "combined");
        return score !== null && score >= 6;
      }).length,
    [pointFeatures]
  );
  const selectedIntelBreakdown = useMemo(() => {
    if (sceneId !== "intel" || !selectedFeature) return null;
    const properties = asRecord(selectedFeature.properties);
    const weatherScore = getNumericValue(asRecord(properties?.weather)?.score);
    const conflictScore = getNumericValue(asRecord(properties?.conflict)?.score);
    const newsCount = getNumericValue(asRecord(properties?.news)?.count) || 0;
    return `Weather ${weatherScore !== null ? `${Math.round(weatherScore)}/10` : "n/a"} • Conflict ${conflictScore !== null ? `${Math.round(conflictScore)}/10` : "n/a"} • ${Math.round(newsCount)} headlines`;
  }, [sceneId, selectedFeature]);
  const availableLenses = useMemo(() => {
    const raw = scene?.meta?.available_lenses || [];
    const wanted = new Set(
      raw
        .filter((value): value is string => typeof value === "string")
        .map((value) => value.toLowerCase())
    );
    if (!wanted.size) return INTEL_LENS_OPTIONS;
    return INTEL_LENS_OPTIONS.filter((option) => wanted.has(option.id));
  }, [scene?.meta?.available_lenses]);

  if (!isOpen || !activeScene) return null;

  return (
    <div className="globe-overlay" data-testid="globe-overlay">
      <div className="globe-overlay__backdrop" />
      <div className="globe-overlay__stage">
        {scene ? (
          <GlobeScene
            cameraPreset={sceneState.cameraPreset}
            intelLens={sceneState.intelLens}
            scene={scene}
            sceneId={sceneId}
            selectedFocus={selectedFocus}
            selectedId={selectedId}
            reducedMotion={reducedMotion}
            qualityFactor={qualityFactor}
            onQualityChange={setQualityFactor}
            onSelect={(id) => {
              setSelectedId(id);
              setCameraPreset("focus");
            }}
          />
        ) : sceneUnavailable ? (
          <div className="globe-overlay__loading">
            <AlertTriangle size={26} className="text-amber-300" />
            <p>Scene unavailable.</p>
            <p className="globe-overlay__status-copy">
              {hasTrackerFallback
                ? "The immersive globe could not load from the primary scene route or the tracker snapshot fallback."
                : "The immersive globe could not load from the primary regional scene route."}
            </p>
            <div className="globe-overlay__actions">
              <button type="button" onClick={refresh} className="globe-action-button">
                Retry Scene
              </button>
              <button type="button" onClick={closeScene} className="globe-action-button">
                Close Globe
              </button>
            </div>
          </div>
        ) : (
          <div className="globe-overlay__loading">
            <Orbit size={26} className="animate-spin text-emerald-300" />
            <p>Loading immersive globe...</p>
          </div>
        )}
      </div>

      <div className="globe-hud globe-hud--left">
        <div className="globe-panel">
          <div className="globe-panel__header">
            <div>
              <p className="tag text-[11px] uppercase tracking-[0.22em] text-emerald-300/90">
                OSINT Globe
              </p>
              <h2 className="globe-panel__title">
                {scene?.title || activeScene.label}
              </h2>
            </div>
            <button
              type="button"
              onClick={closeScene}
              className="globe-icon-button"
              aria-label="Close globe"
            >
              <X size={16} />
            </button>
          </div>
          <p className="globe-panel__copy">{activeScene.description}</p>
          <div className="globe-badges">
            <span className="globe-badge">
              <RadioTower size={12} />
              {sceneId === "intel"
                ? `${scene?.timeline?.point_count || pointFeatures.length || 0} regional nodes`
                : `${scene?.timeline?.point_count || pointFeatures.length || 0} live points`}
            </span>
            {sceneId === "intel" ? (
              <span className="globe-badge">
                <AlertTriangle size={12} />
                {intelHighRiskCount} elevated regions
              </span>
            ) : (
              <span className="globe-badge">
                <Route size={12} />
                {scene?.timeline?.trail_count || pathLayer?.features.length || 0} trails
              </span>
            )}
            <span className="globe-badge">
              {sceneId === "intel" ? getLensLabel(sceneState.intelLens) : scene?.timeline?.mode || sceneState.trackerMode}
            </span>
            <span className="globe-badge">{getQualityLabel(qualityFactor, reducedMotion)}</span>
          </div>
        </div>

        <div className="globe-panel globe-panel--compact">
          <p className="globe-panel__label">{sceneId === "intel" ? "Signal Lens" : "Scene Scope"}</p>
          {sceneId === "intel" ? (
            <div className="globe-toggle-group">
              {availableLenses.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  data-testid={`globe-lens-${option.id}`}
                  onClick={() => setIntelLens(option.id)}
                  className={
                    option.id === sceneState.intelLens
                      ? "globe-toggle globe-toggle--active"
                      : "globe-toggle"
                  }
                >
                  {option.label}
                </button>
              ))}
            </div>
          ) : (
            <div className="globe-toggle-group">
              {TRACKER_MODE_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  data-testid={`globe-mode-${option.id}`}
                  onClick={() => {
                    setTrackerMode(option.id);
                    setCameraPreset("overview");
                    setSelectedId(null);
                  }}
                  className={
                    option.id === sceneState.trackerMode
                      ? "globe-toggle globe-toggle--active"
                      : "globe-toggle"
                  }
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
          <p className="globe-panel__label">Camera Preset</p>
          <div className="globe-toggle-group">
            {CAMERA_PRESET_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                data-testid={`globe-preset-${option.id}`}
                onClick={() => setCameraPreset(option.id)}
                className={
                  option.id === sceneState.cameraPreset
                    ? "globe-toggle globe-toggle--active"
                    : "globe-toggle"
                }
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="globe-panel globe-panel--compact">
          <p className="globe-panel__label">Scene Status</p>
          <p className="globe-panel__metric">
            {loading && !scene
              ? "Loading"
              : sceneUnavailable
                ? "Unavailable"
                : formatTimestamp(scene?.meta?.timestamp)}
          </p>
          <p className="globe-panel__copy">
            {sceneUnavailable
              ? "The immersive scene could not be recovered. Retry or close the overlay."
              : error && fallbackScene
                ? "Primary scene route unavailable. Snapshot fallback active."
                : reducedMotion
                  ? "Reduced-motion mode is active for accessibility and stable visual review."
                  : sceneId === "intel"
                    ? "Regional signal scene active with adaptive quality controls."
                    : "Immersive overlay active with adaptive quality controls."}
          </p>
          {warnings.length ? (
            <div className="globe-warning-list">
              {warnings.slice(0, 3).map((warning) => (
                <p key={warning} className="globe-warning">
                  <AlertTriangle size={12} />
                  {warning}
                </p>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className="globe-hud globe-hud--right">
        <div className="globe-panel">
          <div className="globe-panel__header">
            <div>
              <p className="globe-panel__label">
                {sceneId === "intel" ? "Regional Nodes" : "Focus Targets"}
              </p>
              <p className="globe-panel__copy">
                {sceneId === "intel"
                  ? "Pivot across regions and compare weather, conflict, and news pressure."
                  : "Rotate freely or follow a live signal."}
              </p>
            </div>
          </div>
          <div className="globe-target-list">
            {(scene?.focus_targets || []).map((target) => (
              <button
                key={target.id}
                type="button"
                onClick={() => {
                  setSelectedId(target.id);
                  setCameraPreset("focus");
                }}
                className={
                  target.id === selectedId
                    ? "globe-target globe-target--active"
                    : "globe-target"
                }
              >
                <span>{target.label || target.id}</span>
                <span className="globe-target__meta">
                  {getFocusTargetMeta(sceneId, target)}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="globe-panel globe-panel--compact">
          <p className="globe-panel__label">
            {sceneId === "intel" ? "Selected Region" : "Selected Signal"}
          </p>
          <p className="globe-panel__metric">
            {selectedFocus?.label || "No focus selected"}
          </p>
          <p className="globe-panel__copy">
            {sceneId === "intel"
              ? getSelectedIntelCopy(selectedFeature, sceneState.intelLens)
              : selectedFocus
                ? `${String(selectedFocus.kind || "signal").toUpperCase()} • ${selectedFocus.category || "unknown"}`
                : "Choose a focus target to inspect the live layer."}
          </p>
          {selectedIntelBreakdown ? (
            <p className="globe-panel__copy">{selectedIntelBreakdown}</p>
          ) : null}
          <button type="button" onClick={refresh} className="globe-action-button">
            Refresh Scene
          </button>
        </div>
      </div>
    </div>
  );
}
