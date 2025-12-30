import { useSyncExternalStore } from "react";
import { apiGet } from "./api";

type MetricsPayload = {
  metrics?: {
    disk_total_gb?: number | null;
    disk_used_gb?: number | null;
    disk_free_gb?: number | null;
    disk_percent?: number | null;
    cpu_percent?: number | null;
    mem_percent?: number | null;
    mem_used_gb?: number | null;
    mem_total_gb?: number | null;
    swap_percent?: number | null;
  };
};

type MetricsSnapshot = {
  metrics: MetricsPayload["metrics"] | null;
  error: string | null;
  lastUpdated: number;
};

const listeners = new Set<() => void>();
let snapshot: MetricsSnapshot = { metrics: null, error: null, lastUpdated: 0 };
let inflight: Promise<void> | null = null;
let timer: number | null = null;

const INTERVAL_MS = 60000;

async function refreshMetrics() {
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const payload = await apiGet<MetricsPayload>("/api/tools/diagnostics", 0);
      snapshot = {
        metrics: payload.metrics ?? null,
        error: null,
        lastUpdated: Date.now()
      };
    } catch (err) {
      snapshot = {
        metrics: snapshot.metrics,
        error: err instanceof Error ? err.message : "Unknown error",
        lastUpdated: Date.now()
      };
    } finally {
      inflight = null;
      listeners.forEach((listener) => listener());
    }
  })();
  return inflight;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!timer && typeof window !== "undefined") {
    refreshMetrics();
    timer = window.setInterval(refreshMetrics, INTERVAL_MS);
  }
  return () => {
    listeners.delete(listener);
    if (!listeners.size && timer) {
      window.clearInterval(timer);
      timer = null;
    }
  };
}

function getSnapshot() {
  return snapshot;
}

export function useSystemMetrics() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
