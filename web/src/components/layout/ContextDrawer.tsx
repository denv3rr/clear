import { NavLink } from "react-router-dom";
import { Pause, Play } from "lucide-react";
import { useApi } from "../../lib/api";
import { useSystemMetrics } from "../../lib/systemMetrics";
import { useTrackerPause } from "../../lib/trackerPause";
import { MeterBar } from "../ui/Charts";

type ContextDrawerProps = {
  variant?: "inline" | "overlay";
  onClose?: () => void;
};

type DiagnosticsPayload = {
  feeds?: {
    flights?: { configured?: boolean };
    opensky?: { credentials_set?: boolean };
  };
  trackers?: { count?: number; warning_count?: number; warnings?: string[] };
  metrics?: {
    cpu_percent?: number | null;
    mem_percent?: number | null;
    disk_percent?: number | null;
    swap_percent?: number | null;
  };
  system?: { hostname?: string; platform?: string };
};

export function ContextDrawer({ variant = "inline", onClose }: ContextDrawerProps) {
  const { data: diagnostics } = useApi<DiagnosticsPayload>("/api/tools/diagnostics", {
    interval: 60000
  });
  const { data: health } = useApi<{ status?: string }>("/api/health", {
    interval: 30000
  });
  const { paused, toggle } = useTrackerPause();

  const trackerWarnings = diagnostics?.trackers?.warnings || [];
  const trackerCount = diagnostics?.trackers?.count ?? 0;
  const warningCount = diagnostics?.trackers?.warning_count ?? 0;
  const status = health?.status === "ok" ? "Online" : "Degraded";
  const feedConfigured = diagnostics?.feeds?.flights?.configured;
  const openskyConfigured = diagnostics?.feeds?.opensky?.credentials_set;
  const { metrics } = useSystemMetrics();

  const panelClass =
    variant === "overlay"
      ? "glass-panel rounded-t-2xl rounded-b-none sm:rounded-2xl p-5 space-y-4"
      : "glass-panel rounded-2xl p-5 space-y-4";
  const panel = (
    <div className={panelClass}>
      <div className="flex items-center justify-between">
        <p className="tag text-xs text-green-300">SYSTEM STATUS</p>
        {variant === "overlay" ? (
          <button
            className="text-xs text-slate-200 hover:text-green-300"
            type="button"
            onClick={onClose}
          >
            Close
          </button>
        ) : null}
      </div>
      {status ? (
        <span
          className={`inline-flex items-center rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.2em] ${
            status === "Online"
              ? "border-green-500/50 text-green-200"
              : "border-rose-500/60 text-rose-300"
          }`}
        >
          API {status}
        </span>
      ) : null}
      <div>
        <p className="text-sm text-slate-300 mt-1">
          Trackers: {trackerCount} • Warnings: {warningCount}
        </p>
        {paused ? (
          <p className="text-[11px] text-amber-300 mt-1">
            Tracker updates paused.
          </p>
        ) : null}
        <p className="text-[11px] text-slate-400 mt-2">
          {feedConfigured
            ? "Flight feed configured"
            : openskyConfigured
            ? "OpenSky credentials active"
            : "OpenSky anonymous mode"}
        </p>
        <p className="text-[11px] text-slate-400">
          {diagnostics?.system?.hostname
            ? `${diagnostics.system.hostname} • ${diagnostics.system.platform || "system"}`
            : "System info pending."}
        </p>
      </div>
      <div className="rounded-xl border border-slate-700 px-3 py-2 text-[11px] text-slate-300">
        {warningCount > 0 ? "Recent tracker warnings detected." : "All systems nominal."}
      </div>
      <div className="space-y-2">
        <p className="text-[11px] text-slate-400 uppercase tracking-[0.2em]">Tracker Controls</p>
        <button
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs transition ${
            paused
              ? "border-amber-400/70 text-amber-200 hover:border-amber-300"
              : "border-slate-700 text-slate-100 hover:border-green-500 hover:text-green-500"
          }`}
          type="button"
          onClick={toggle}
        >
          {paused ? <Play size={14} /> : <Pause size={14} />}
          {paused ? "Resume Trackers" : "Pause Trackers"}
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 text-[11px] text-slate-300">
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400">CPU</p>
          <MeterBar value={metrics?.cpu_percent ?? 0} height={40} />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Memory</p>
          <MeterBar value={metrics?.mem_percent ?? 0} height={40} color="#36c9f8" />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Disk</p>
          <MeterBar value={metrics?.disk_percent ?? 0} height={40} color="#f5b94c" />
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Swap</p>
          <MeterBar value={metrics?.swap_percent ?? 0} height={40} color="#a3e635" />
        </div>
      </div>
      {trackerWarnings.length ? (
        <div className="rounded-xl border border-slate-700 px-3 py-2 text-[11px] text-slate-300">
          {trackerWarnings[0]}
        </div>
      ) : null}
      <div className="space-y-2">
        <p className="text-[11px] text-slate-400 uppercase tracking-[0.2em]">Quick Actions</p>
        <div className="flex flex-wrap gap-2 text-xs">
          <NavLink
            to="/trackers"
            className="rounded-full border border-slate-700 px-3 py-1 text-slate-100 hover:text-green-500"
          >
            Live Trackers
          </NavLink>
          <NavLink
            to="/news"
            className="rounded-full border border-slate-700 px-3 py-1 text-slate-100 hover:text-green-500"
          >
            News Feed
          </NavLink>
          <NavLink
            to="/reports"
            className="rounded-full border border-slate-700 px-3 py-1 text-slate-100 hover:text-green-500"
          >
            Reports
          </NavLink>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-300">
        <NavLink to="/tools" className="hover:text-green-500">
          Diagnostics
        </NavLink>
        <span>•</span>
        <NavLink to="/settings" className="hover:text-green-500">
          Settings
        </NavLink>
      </div>
    </div>
  );

  if (variant === "overlay") {
    return (
      <div
        className="fixed inset-0 z-50 flex items-end justify-center bg-black/80 backdrop-blur-sm sm:items-center sm:justify-end"
        onClick={onClose}
      >
        <div
          className="w-full p-6 sm:h-full sm:max-w-sm"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="sm:h-full sm:flex sm:items-center">{panel}</div>
        </div>
      </div>
    );
  }

  return <aside className="w-80 space-y-6">{panel}</aside>;
}
