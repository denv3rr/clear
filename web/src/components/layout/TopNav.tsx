import { NavLink } from "react-router-dom";
import { Pause, Play } from "lucide-react";
import { useTrackerPause } from "../../lib/trackerPause";

type NavItem = {
  label: string;
  icon: React.ComponentType<{ size?: number }>;
  path: string;
};

type TopNavProps = {
  items: NavItem[];
  onToggleContext?: () => void;
};

export function TopNav({ items, onToggleContext }: TopNavProps) {
  const utilityPaths = new Set(["/tools", "/settings"]);
  const primaryItems = items.filter((item) => !utilityPaths.has(item.path));
  const utilityItems = items.filter((item) => utilityPaths.has(item.path));
  const { paused, toggle } = useTrackerPause();

  return (
    <header className="border-b border-slate-900/80 bg-ink-950/95 backdrop-blur">
      <div className="flex items-center gap-6 py-4 pl-[44px] pr-6 md:pl-[60px] md:pr-10 lg:pl-[68px] lg:pr-12">
        <div className="flex items-center gap-3">
          <span className="text-lg font-semibold tracking-tight">[ CLEAR ]</span>
          <span className="hidden text-xs text-slate-500 sm:inline">
            Markets • Risk • Trackers
          </span>
        </div>
        <nav className="flex-1">
          <div className="flex gap-2 overflow-x-auto py-1">
            {primaryItems.map(({ label, icon: Icon, path }) => (
              <NavLink
                key={label}
                to={path}
                className={({ isActive }) =>
                  [
                    "flex items-center gap-2 rounded-full px-4 py-2 text-sm transition",
                    isActive
                      ? "bg-slate-900/80 text-white"
                      : "text-slate-300 hover:bg-slate-900/50"
                  ].join(" ")
                }
              >
                <Icon size={16} />
                <span className="whitespace-nowrap">{label}</span>
              </NavLink>
            ))}
          </div>
        </nav>
        <div className="flex items-center gap-2">
          <div className="hidden md:flex items-center gap-2">
            {utilityItems.map(({ label, icon: Icon, path }) => (
              <NavLink
                key={label}
                to={path}
                className={({ isActive }) =>
                  [
                    "flex items-center gap-2 rounded-full px-3 py-2 text-xs transition",
                    isActive
                      ? "bg-slate-900/80 text-white"
                      : "text-slate-300 hover:bg-slate-900/50"
                  ].join(" ")
                }
              >
                <Icon size={15} />
                <span className="whitespace-nowrap">{label}</span>
              </NavLink>
            ))}
          </div>
          <button
            className={`rounded-full border px-3 py-2 text-xs transition ${
              paused
                ? "border-amber-400/70 text-amber-200 hover:border-amber-300"
                : "border-slate-800/80 text-slate-300 hover:border-slate-700 hover:text-white"
            }`}
            type="button"
            onClick={toggle}
          >
            <span className="flex items-center gap-2">
              {paused ? <Play size={14} /> : <Pause size={14} />}
              {paused ? "Resume Trackers" : "Pause Trackers"}
            </span>
          </button>
          <button
            className="rounded-full border border-slate-800/80 px-4 py-2 text-xs text-slate-300 hover:border-slate-700 hover:text-white"
            type="button"
            onClick={onToggleContext}
          >
            Context
          </button>
        </div>
      </div>
    </header>
  );
}
