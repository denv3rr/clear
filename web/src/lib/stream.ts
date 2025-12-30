import { useEffect, useRef, useState } from "react";
import { DEMO_MODE, getMockTrackerSnapshot } from "./mockData";
import { useTrackerPause } from "./trackerPause";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const ENV_API_KEY = import.meta.env.VITE_API_KEY;

type StreamOptions = {
  interval?: number;
  enabled?: boolean;
  mode?: "combined" | "flights" | "ships";
};

export function useTrackerStream<T>(options: StreamOptions = {}) {
  const { interval = 5, enabled = true, mode = "combined" } = options;
  const [data, setData] = useState<T | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const { paused } = useTrackerPause();

  useEffect(() => {
    if (!enabled || paused) {
      setConnected(false);
      setError(null);
      return;
    }
    if (DEMO_MODE) {
      setConnected(true);
      setError(null);
      setData(getMockTrackerSnapshot(mode) as T);
      if (!interval) return;
      const timer = setInterval(() => {
        setData(getMockTrackerSnapshot(mode) as T);
      }, interval * 1000);
      return () => clearInterval(timer);
    }
    const params = new URLSearchParams();
    params.set("mode", mode);
    params.set("interval", String(interval));
    try {
      const apiKey = localStorage.getItem("clear_api_key");
      if (apiKey) {
        params.set("api_key", apiKey);
      } else if (ENV_API_KEY) {
        params.set("api_key", ENV_API_KEY);
      }
    } catch {
      if (ENV_API_KEY) {
        params.set("api_key", ENV_API_KEY);
      }
      // ignore
    }
    const wsUrl = API_BASE.replace("http", "ws") + `/ws/trackers?${params.toString()}`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    setError(null);
    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };
    ws.onclose = (event) => {
      setConnected(false);
      if (event.code === 1008) {
        setError("WebSocket rejected. Check API key settings.");
      } else if (event.code === 1006) {
        setError("WebSocket closed unexpectedly. Check API base and auth.");
      }
    };
    ws.onerror = () => {
      setConnected(false);
      setError("WebSocket connection failed. Check API base and auth.");
    };
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as T;
        setData(payload);
      } catch {
        setConnected(false);
        setError("WebSocket payload parsing failed.");
      }
    };

    return () => {
      ws.close();
    };
  }, [enabled, interval, mode, paused]);

  return { data, connected, error };
}
