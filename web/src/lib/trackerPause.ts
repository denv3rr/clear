import { useEffect, useState } from "react";

const PAUSE_KEY = "clear_tracker_paused";
const PAUSE_EVENT = "clear:tracker-pause";

export function getTrackerPaused(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(PAUSE_KEY) === "true";
  } catch {
    return false;
  }
}

export function setTrackerPaused(value: boolean): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(PAUSE_KEY, value ? "true" : "false");
  } catch {
    return;
  }
  try {
    window.dispatchEvent(new CustomEvent(PAUSE_EVENT, { detail: value }));
  } catch {
    // no-op
  }
}

export function useTrackerPause() {
  const [paused, setPaused] = useState(getTrackerPaused());

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === PAUSE_KEY) {
        setPaused(event.newValue === "true");
      }
    };
    const handleEvent = (event: Event) => {
      if (event instanceof CustomEvent) {
        setPaused(Boolean(event.detail));
      }
    };
    window.addEventListener("storage", handleStorage);
    window.addEventListener(PAUSE_EVENT, handleEvent as EventListener);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(PAUSE_EVENT, handleEvent as EventListener);
    };
  }, []);

  return {
    paused,
    setPaused: (value: boolean) => setTrackerPaused(value),
    toggle: () => setTrackerPaused(!getTrackerPaused())
  };
}
