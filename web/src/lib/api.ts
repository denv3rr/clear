import { useEffect, useMemo, useRef, useState } from "react";

const runtimeHost =
  typeof window !== "undefined" && window.location.hostname
    ? window.location.hostname
    : "127.0.0.1";
const API_BASE =
  import.meta.env.VITE_API_BASE || `http://${runtimeHost}:8000`;

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
    return null;
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
  const headers: Record<string, string> = {};
  const apiKey = getApiKey();
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

  const fetchData = useMemo(
    () => async () => {
      if (!enabled) return;
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
    [enabled, path, ttl]
  );

  useEffect(() => {
    fetchData();
    if (!interval || !enabled) return;
    const timer = setInterval(fetchData, interval);
    return () => clearInterval(timer);
  }, [fetchData, interval, enabled]);

  useEffect(() => () => abortRef.current?.abort(), []);

  return { data, loading, error, refresh: fetchData };
}
