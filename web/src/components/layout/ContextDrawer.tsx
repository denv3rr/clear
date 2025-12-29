import { NavLink } from "react-router-dom";
import { useApi } from "../../lib/api";

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
  system?: { hostname?: string; platform?: string };
};

export function ContextDrawer({ variant = "inline", onClose }: ContextDrawerProps) {
  const { data: diagnostics } = useApi<DiagnosticsPayload>("/api/tools/diagnostics", {
    interval: 60000
  });
  const { data: health } = useApi<{ status?: string }>("/api/health", {
    interval: 30000
  });

  const trackerWarnings = diagnostics?.trackers?.warnings || [];
  const trackerCount = diagnostics?.trackers?.count ?? 0;
  const warningCount = diagnostics?.trackers?.warning_count ?? 0;
  const status = health?.status === "ok" ? "Online" : "Degraded";
  const feedConfigured = diagnostics?.feeds?.flights?.configured;
  const openskyConfigured = diagnostics?.feeds?.opensky?.credentials_set;

  const panelClass =
    variant === "overlay"
      ? "glass-panel rounded-t-2xl rounded-b-none sm:rounded-2xl p-5 space-y-4"
      : "glass-panel rounded-2xl p-5 space-y-4";
  const panel = (
    <div className={panelClass}>
      <div className="flex items-center justify-between">
        <p className="tag text-xs text-emerald-300">SYSTEM STATUS</p>
        {variant === "overlay" ? (
          <button
            className="text-xs text-slate-400 hover:text-emerald-300"
            type="button"
            onClick={onClose}
          >
            Close
          </button>
        ) : null}
      </div>
      <div>
        <h3 className="text-lg font-semibold">{status}</h3>
        <p className="text-sm text-slate-400 mt-1">
          Trackers: {trackerCount} • Warnings: {warningCount}
        </p>
        <p className="text-[11px] text-slate-500 mt-2">
          {feedConfigured
            ? "Flight feed configured"
            : openskyConfigured
            ? "OpenSky credentials active"
            : "OpenSky anonymous mode"}
        </p>
        <p className="text-[11px] text-slate-500">
          {diagnostics?.system?.hostname
            ? `${diagnostics.system.hostname} • ${diagnostics.system.platform || "system"}`
            : "System info pending."}
        </p>
      </div>
      <div className="rounded-xl border border-slate-900/70 px-3 py-2 text-[11px] text-slate-400">
        {warningCount > 0 ? "Recent tracker warnings detected." : "All systems nominal."}
      </div>
      {trackerWarnings.length ? (
        <div className="rounded-xl border border-slate-800/70 px-3 py-2 text-[11px] text-slate-400">
          {trackerWarnings[0]}
        </div>
      ) : null}
      <div className="space-y-2">
        <p className="text-[11px] text-slate-500 uppercase tracking-[0.2em]">Quick Actions</p>
        <div className="flex flex-wrap gap-2 text-xs">
          <NavLink
            to="/trackers"
            className="rounded-full border border-slate-800/70 px-3 py-1 text-slate-300 hover:text-white"
          >
            Live Trackers
          </NavLink>
          <NavLink
            to="/news"
            className="rounded-full border border-slate-800/70 px-3 py-1 text-slate-300 hover:text-white"
          >
            News Feed
          </NavLink>
          <NavLink
            to="/reports"
            className="rounded-full border border-slate-800/70 px-3 py-1 text-slate-300 hover:text-white"
          >
            Reports
          </NavLink>
        </div>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <NavLink to="/tools" className="hover:text-white">
          Diagnostics
        </NavLink>
        <span>•</span>
        <NavLink to="/settings" className="hover:text-white">
          Settings
        </NavLink>
      </div>
    </div>
  );

  if (variant === "overlay") {
    return (
      <div
        className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 backdrop-blur-sm sm:items-center sm:justify-end"
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
