import { useEffect, useRef, useState } from "react";
import { DEMO_MODE, getMockTrackerSnapshot } from "./mockData";

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
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;
    if (DEMO_MODE) {
      setConnected(true);
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

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as T;
        setData(payload);
      } catch {
        setConnected(false);
      }
    };

    return () => {
      ws.close();
    };
  }, [enabled, interval, mode]);

  return { data, connected };
}
