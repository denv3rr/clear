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
const ENCRYPTED_PREFIX = "enc:v1:";

let sessionCryptoKeyPromise: Promise<CryptoKey> | null = null;

function getSessionCryptoKey(): Promise<CryptoKey> {
  if (!sessionCryptoKeyPromise) {
    sessionCryptoKeyPromise = crypto.subtle.generateKey(
      { name: "AES-GCM", length: 256 },
      false,
      ["encrypt", "decrypt"]
    );
  }
  return sessionCryptoKeyPromise;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function encryptApiKey(value: string): Promise<string> {
  const key = await getSessionCryptoKey();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const plaintext = new TextEncoder().encode(value);
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plaintext);
  return `${ENCRYPTED_PREFIX}${bytesToBase64(iv)}:${bytesToBase64(new Uint8Array(ciphertext))}`;
}

async function decryptApiKey(payload: string): Promise<string | null> {
  if (!payload.startsWith(ENCRYPTED_PREFIX)) return payload;
  const encoded = payload.slice(ENCRYPTED_PREFIX.length);
  const [ivB64, dataB64] = encoded.split(":");
  if (!ivB64 || !dataB64) return null;
  const iv = base64ToBytes(ivB64);
  const data = base64ToBytes(dataB64);
  const key = await getSessionCryptoKey();
  const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, data);
  return new TextDecoder().decode(plaintext);
}

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

export async function getApiKey(): Promise<string | null> {
  try {
    const sessionValue = sessionStorage.getItem(SESSION_KEY);
    if (sessionValue) {
      try {
        return await decryptApiKey(sessionValue);
      } catch {
        sessionStorage.removeItem(SESSION_KEY);
      }
    }

    const localValue = localStorage.getItem(LOCAL_KEY);
    if (localValue) {
      try {
        return await decryptApiKey(localValue);
      } catch {
        localStorage.removeItem(LOCAL_KEY);
      }
    }

    return ENV_API_KEY || null;
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

export async function setApiKey(
  value: string,
  options: { persist?: boolean } = {}
): Promise<void> {
  try {
    localStorage.removeItem(LOCAL_KEY);
    sessionStorage.removeItem(SESSION_KEY);
    const encrypted = await encryptApiKey(value);
    if (options.persist) {
      localStorage.setItem(LOCAL_KEY, encrypted);
    } else {
      sessionStorage.setItem(SESSION_KEY, encrypted);
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
