import { useEffect, useMemo, useRef, useState } from "react";
import { DEMO_MODE, getMockResponse } from "./mockData";
import { getTrackerPaused, useTrackerPause } from "./trackerPause";

const runtimeHost =
  typeof window !== "undefined" && window.location.hostname
    ? window.location.hostname
    : "127.0.0.1";
const API_BASE =
  import.meta.env.VITE_API_BASE || `http://${runtimeHost}:8000`;
const ENV_API_KEY = import.meta.env.VITE_API_KEY;

export function getApiBase(): string {
  return API_BASE;
}

type CacheEntry<T> = {
  ts: number;
  ttl: number;
  data: T;
};

const cache = new Map<string, CacheEntry<unknown>>();

function cacheKey(path: string) {
  return `${API_BASE}${path}`;
}

function applyDemoOverrides(path: string) {
  if (typeof window === "undefined") return path;
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("demo_empty");
  if (!raw) return path;
  const targets = new Set(
    raw
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  );
  if (!targets.size) return path;
  const url = new URL(path, "http://mock.local");
  if (targets.has("clients") && url.pathname === "/api/clients") {
    url.searchParams.set("empty", "true");
  }
  if (targets.has("news") && url.pathname === "/api/intel/news") {
    url.searchParams.set("empty", "true");
  }
  if (targets.has("trackers") && url.pathname === "/api/trackers/snapshot") {
    url.searchParams.set("empty", "true");
  }
  if (targets.has("summary") && url.pathname === "/api/intel/summary") {
    url.searchParams.set("empty", "true");
  }
  return `${url.pathname}${url.search}`;
}

function isDemoOverride(): boolean {
  if (typeof window === "undefined") return false;
  if (!import.meta.env.DEV) return false;
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("demo");
  return raw === "true" || raw === "1";
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error("Invalid JSON response");
  }
}

export function getApiKey(): string | null {
  try {
    return localStorage.getItem("clear_api_key");
  } catch {
    return ENV_API_KEY || null;
  }
}

export function setApiKey(value: string): void {
  try {
    localStorage.setItem("clear_api_key", value);
  } catch {
    return;
  }
}

export function clearApiKey(): void {
  try {
    localStorage.removeItem("clear_api_key");
  } catch {
    return;
  }
}

export async function apiGet<T>(path: string, ttl = 0, signal?: AbortSignal): Promise<T> {
  const key = cacheKey(path);
  if (ttl > 0) {
    const existing = cache.get(key) as CacheEntry<T> | undefined;
    if (existing && Date.now() - existing.ts < existing.ttl) {
      return existing.data;
    }
  }
  if (path.startsWith("/api/trackers") && getTrackerPaused()) {
    const existing = cache.get(key) as CacheEntry<T> | undefined;
    if (existing) {
      return existing.data;
    }
    throw new Error("Tracker updates paused.");
  }
  const demoMode = DEMO_MODE || isDemoOverride();
  if (demoMode) {
    const payload = getMockResponse(applyDemoOverrides(path)) as T;
    if (ttl > 0) {
      cache.set(key, { ts: Date.now(), ttl, data: payload });
    }
    return payload;
  }
  const headers: Record<string, string> = {};
  const apiKey = getApiKey() || ENV_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { headers, signal });
  } catch (err) {
    const detail = err instanceof Error ? err.message : "Network error";
    const cspHint = /failed to fetch|networkerror/i.test(detail)
      ? " Check CSP connect-src allows the API base."
      : "";
    throw new Error(`API unreachable at ${API_BASE}. ${detail}${cspHint}`);
  }
  if (!response.ok) {
    throw new Error(`API ${response.status}`);
  }
  const payload = await parseJson<T>(response);
  if (ttl > 0) {
    cache.set(key, { ts: Date.now(), ttl, data: payload });
  }
  return payload;
}

type WriteMethod = "POST" | "PATCH" | "PUT" | "DELETE";

async function apiWrite<T>(path: string, method: WriteMethod, body?: unknown): Promise<T> {
  if (DEMO_MODE || isDemoOverride()) {
    throw new Error("Demo mode: write operations are disabled.");
  }
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const apiKey = getApiKey() || ENV_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined
    });
  } catch (err) {
    const detail = err instanceof Error ? err.message : "Network error";
    throw new Error(`API unreachable at ${API_BASE}. ${detail}`);
  }
  if (!response.ok) {
    throw new Error(`API ${response.status}`);
  }
  return parseJson<T>(response);
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiWrite<T>(path, "POST", body);
}

export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return apiWrite<T>(path, "PATCH", body);
}

type UseApiOptions = {
  ttl?: number;
  interval?: number;
  enabled?: boolean;
};

export function useApi<T>(path: string, options: UseApiOptions = {}) {
  const { ttl = 0, interval = 0, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const { paused } = useTrackerPause();
  const trackerPaused = paused && path.startsWith("/api/trackers");

  const fetchData = useMemo(
    () => async () => {
      if (!enabled || trackerPaused) return;
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      try {
        setLoading(true);
        const payload = await apiGet<T>(path, ttl, abortRef.current.signal);
        setData(payload);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [enabled, path, ttl, trackerPaused]
  );

  useEffect(() => {
    if (trackerPaused) {
      setLoading(false);
      return;
    }
    fetchData();
    if (!interval || !enabled) return;
    const timer = setInterval(fetchData, interval);
    return () => clearInterval(timer);
  }, [fetchData, interval, enabled, trackerPaused]);

  useEffect(() => () => abortRef.current?.abort(), []);

  return { data, loading, error, refresh: fetchData };
}
