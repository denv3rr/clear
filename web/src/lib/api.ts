import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTrackerPause } from "./trackerPause";

const runtimeHost =
  typeof window !== "undefined" && window.location.hostname
    ? window.location.hostname
    : "127.0.0.1";
const API_BASE =
  import.meta.env.VITE_API_BASE || `http://${runtimeHost}:8000`;
const ENV_API_KEY = import.meta.env.VITE_API_KEY;
const LOCAL_KEY = "clear_api_key";
const SESSION_KEY = "clear_api_key_session";

type ApiKeyScope = "session" | "local" | "env" | "none";

export function getApiBase(): string {
  return API_BASE;
}

type CacheEntry<T> = {
  ts: number;
  ttl: number;
  data: T;
};

type ApiMeta = {
  warnings?: string[];
};

const cache = new Map<string, CacheEntry<unknown>>();

function cacheKey(path: string) {
  return `${API_BASE}${path}`;
}

export function extractWarnings(payload: unknown): string[] {
  if (!payload || typeof payload !== "object") return [];
  const meta = (payload as { meta?: ApiMeta }).meta;
  if (!meta || !Array.isArray(meta.warnings)) return [];
  return meta.warnings.filter((item): item is string => typeof item === "string");
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  try {
    return JSON.parse(text) as T;
  } catch (err) {
    const detail = err instanceof Error ? err.message : "Unknown error";
    throw new Error(`Invalid JSON response: ${detail}`);
  }
}

export function getApiKey(): string | null {
  try {
    return (
      sessionStorage.getItem(SESSION_KEY) ||
      localStorage.getItem(LOCAL_KEY) ||
      ENV_API_KEY ||
      null
    );
  } catch {
    return ENV_API_KEY || null;
  }
}

export function getApiKeyScope(): ApiKeyScope {
  try {
    if (sessionStorage.getItem(SESSION_KEY)) return "session";
    if (localStorage.getItem(LOCAL_KEY)) return "local";
  } catch {
    return ENV_API_KEY ? "env" : "none";
  }
  return ENV_API_KEY ? "env" : "none";
}

export function setApiKey(
  value: string,
  options: { persist?: boolean } = {}
): void {
  try {
    localStorage.removeItem(LOCAL_KEY);
    sessionStorage.removeItem(SESSION_KEY);
    if (options.persist) {
      // codeql[js/clear-text-storage-of-sensitive-data]: Operator-chosen local API key for this browser only; no remote secret store exists.
      localStorage.setItem(LOCAL_KEY, value);
    } else {
      // codeql[js/clear-text-storage-of-sensitive-data]: Session-scoped local operator key; cleared when the tab closes.
      sessionStorage.setItem(SESSION_KEY, value);
    }
  } catch {
    return;
  }
}

export function clearApiKey(): void {
  try {
    localStorage.removeItem(LOCAL_KEY);
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    return;
  }
}

export function getAuthHint(): string {
  const scope = getApiKeyScope();
  if (scope === "env") {
    return "API key is set in the environment. Verify CLEAR_WEB_API_KEY matches.";
  }
  if (scope === "local" || scope === "session") {
    return "Check the API key in System settings or clear and re-enter it.";
  }
  return "Set an API key in System settings if CLEAR_WEB_API_KEY is enabled.";
}

function _isAbortError(err: unknown): boolean {
  if (!err) return false;
  if (typeof DOMException !== "undefined" && err instanceof DOMException && err.name === "AbortError") {
    return true;
  }
  if (err instanceof Error) {
    if (err.name === "AbortError") return true;
    return /abort/i.test(err.message);
  }
  return false;
}

function formatApiError(status: number): string {
  if (status === 401 || status === 403) {
    return `API ${status}: authentication required. ${getAuthHint()}`;
  }
  return `API ${status}`;
}

export async function apiGet<T>(path: string, ttl = 0, signal?: AbortSignal): Promise<T> {
  const key = cacheKey(path);
  if (ttl > 0) {
    const existing = cache.get(key) as CacheEntry<T> | undefined;
    if (existing && Date.now() - existing.ts < existing.ttl) {
      return existing.data;
    }
  }
  const headers: Record<string, string> = {};
  const apiKey = getApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { headers, signal });
  } catch (err) {
    if (signal?.aborted || _isAbortError(err)) {
      throw new DOMException("Aborted", "AbortError");
    }
    const detail = err instanceof Error ? err.message : "Network error";
    const cspHint = /failed to fetch|networkerror/i.test(detail)
      ? " Check CSP connect-src allows the API base."
      : "";
    throw new Error(`API unreachable at ${API_BASE}. ${detail}${cspHint}`);
  }
  if (!response.ok) {
    throw new Error(formatApiError(response.status));
  }
  const payload = await parseJson<T>(response);
  if (ttl > 0) {
    cache.set(key, { ts: Date.now(), ttl, data: payload });
  }
  return payload;
}

type WriteMethod = "POST" | "PATCH" | "PUT" | "DELETE";

async function apiWrite<T>(path: string, method: WriteMethod, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const apiKey = getApiKey();
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
    throw new Error(formatApiError(response.status));
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
  const [warnings, setWarnings] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const requestGen = useRef(0);
  const { paused } = useTrackerPause();
  const trackerPaused = paused && path.startsWith("/api/trackers");

  const fetchData = useMemo(
    () => async () => {
      if (!enabled || trackerPaused) return;
      abortRef.current?.abort();
      const gen = requestGen.current + 1;
      requestGen.current = gen;
      abortRef.current = new AbortController();
      setLoading(true);
      setError(null);
      try {
        const payload = await apiGet<T>(path, ttl, abortRef.current.signal);
        if (gen !== requestGen.current) return;
        setData(payload);
        setWarnings(extractWarnings(payload));
        setError(null);
      } catch (err) {
        if (gen !== requestGen.current || _isAbortError(err)) {
          return;
        }
        setError(err instanceof Error ? err.message : "Unknown error");
        setWarnings([]);
      } finally {
        if (gen === requestGen.current) {
          setLoading(false);
        }
      }
    },
    [enabled, path, ttl, trackerPaused]
  );

  useLayoutEffect(() => {
    if (!enabled || trackerPaused) {
      requestGen.current += 1;
      abortRef.current?.abort();
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
  }, [enabled, path, trackerPaused]);

  useEffect(() => {
    if (trackerPaused) {
      setWarnings([]);
      return;
    }
    if (!enabled) return;
    fetchData();
    if (!interval) return;
    const timer = setInterval(fetchData, interval);
    return () => clearInterval(timer);
  }, [fetchData, interval, enabled, trackerPaused]);

  useEffect(() => () => abortRef.current?.abort(), []);

  return { data, loading, error, warnings, refresh: fetchData };
}
