import {
  createContext,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";
import type { ReactNode } from "react";

const SCENE_STATE_KEY = "clear_scene_state";

export type SceneId = "trackers" | "intel";
export type TrackerSceneMode = "combined" | "flights" | "ships";
export type IntelSceneLens = "combined" | "weather" | "conflict" | "news";
export type SceneCameraPreset = "overview" | "focus";

export type SceneRuntimeState = {
  cameraPreset: SceneCameraPreset;
  intelLens: IntelSceneLens;
  trackerMode: TrackerSceneMode;
};

export type SceneDefinition = {
  id: SceneId;
  label: string;
  description: string;
  buildPath: (state: SceneRuntimeState) => string;
  fallbackStrategy?: "none" | "trackerSnapshot";
};

type SceneContextValue = {
  activeScene: SceneDefinition | null;
  activeScenePath: string | null;
  closeScene: () => void;
  isOpen: boolean;
  openScene: (sceneId?: SceneId) => void;
  sceneState: SceneRuntimeState;
  setCameraPreset: (preset: SceneCameraPreset) => void;
  setIntelLens: (lens: IntelSceneLens) => void;
  setTrackerMode: (mode: TrackerSceneMode) => void;
  toggleScene: (sceneId?: SceneId) => void;
};

const DEFAULT_SCENE_STATE: SceneRuntimeState = {
  intelLens: "combined",
  trackerMode: "combined",
  cameraPreset: "overview"
};

const SCENES: Record<SceneId, SceneDefinition> = {
  trackers: {
    id: "trackers",
    label: "Tracker Globe",
    description: "Live trackers and replay trails rendered on the globe.",
    buildPath: (state) => `/api/osint/scene/trackers?mode=${state.trackerMode}`,
    fallbackStrategy: "trackerSnapshot"
  },
  intel: {
    id: "intel",
    label: "Regional Intel Globe",
    description: "Regional weather, conflict, and news pressure fused into a globe-first OSINT view.",
    buildPath: () => "/api/osint/scene/intel",
    fallbackStrategy: "none"
  }
};

function readStoredSceneState(): SceneRuntimeState {
  if (typeof window === "undefined") return DEFAULT_SCENE_STATE;
  try {
    const raw = window.localStorage.getItem(SCENE_STATE_KEY);
    if (!raw) return DEFAULT_SCENE_STATE;
    const parsed = JSON.parse(raw) as Partial<SceneRuntimeState>;
    const trackerMode = parsed.trackerMode;
    const intelLens = parsed.intelLens;
    const cameraPreset = parsed.cameraPreset;
    return {
      trackerMode:
        trackerMode === "flights" || trackerMode === "ships" || trackerMode === "combined"
          ? trackerMode
          : DEFAULT_SCENE_STATE.trackerMode,
      intelLens:
        intelLens === "weather" ||
        intelLens === "conflict" ||
        intelLens === "news" ||
        intelLens === "combined"
          ? intelLens
          : DEFAULT_SCENE_STATE.intelLens,
      cameraPreset:
        cameraPreset === "focus" || cameraPreset === "overview"
          ? cameraPreset
          : DEFAULT_SCENE_STATE.cameraPreset
    };
  } catch {
    return DEFAULT_SCENE_STATE;
  }
}

const SceneContext = createContext<SceneContextValue | null>(null);

export function SceneProvider({ children }: { children: ReactNode }) {
  const [activeScene, setActiveScene] = useState<SceneDefinition | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [sceneState, setSceneState] = useState<SceneRuntimeState>(readStoredSceneState);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(SCENE_STATE_KEY, JSON.stringify(sceneState));
    } catch {
      // Ignore storage failures and keep runtime-only state.
    }
  }, [sceneState]);

  const openScene = useCallback((sceneId?: SceneId) => {
    const nextSceneId = sceneId || activeScene?.id || "trackers";
    startTransition(() => {
      setActiveScene(SCENES[nextSceneId]);
      setIsOpen(true);
    });
  }, [activeScene?.id]);

  const closeScene = useCallback(() => {
    startTransition(() => {
      setIsOpen(false);
    });
  }, []);

  const toggleScene = useCallback(
    (sceneId?: SceneId) => {
      const nextSceneId = sceneId || activeScene?.id || "trackers";
      if (isOpen && activeScene?.id === nextSceneId) {
        closeScene();
        return;
      }
      openScene(nextSceneId);
    },
    [activeScene?.id, closeScene, isOpen, openScene]
  );

  const setTrackerMode = useCallback((mode: TrackerSceneMode) => {
    startTransition(() => {
      setSceneState((current) => ({
        ...current,
        trackerMode: mode
      }));
    });
  }, []);

  const setIntelLens = useCallback((lens: IntelSceneLens) => {
    startTransition(() => {
      setSceneState((current) => ({
        ...current,
        intelLens: lens
      }));
    });
  }, []);

  const setCameraPreset = useCallback((preset: SceneCameraPreset) => {
    startTransition(() => {
      setSceneState((current) => ({
        ...current,
        cameraPreset: preset
      }));
    });
  }, []);

  const activeScenePath = useMemo(() => {
    if (!activeScene) return null;
    return activeScene.buildPath(sceneState);
  }, [activeScene, sceneState]);

  const value = useMemo(
    () => ({
      activeScene,
      activeScenePath,
      closeScene,
      isOpen,
      openScene,
      sceneState,
      setCameraPreset,
      setIntelLens,
      setTrackerMode,
      toggleScene
    }),
    [
      activeScene,
      activeScenePath,
      closeScene,
      isOpen,
      openScene,
      sceneState,
      setCameraPreset,
      setIntelLens,
      setTrackerMode,
      toggleScene
    ]
  );

  return <SceneContext.Provider value={value}>{children}</SceneContext.Provider>;
}

export function useSceneController() {
  const value = useContext(SceneContext);
  if (!value) {
    throw new Error("useSceneController must be used within a SceneProvider.");
  }
  return value;
}
