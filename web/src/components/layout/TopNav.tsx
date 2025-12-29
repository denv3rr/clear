import { NavLink } from "react-router-dom";

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

  return (
    <header className="border-b border-slate-900/80 bg-ink-950/95 backdrop-blur">
      <div className="flex items-center gap-6 px-6 py-4 md:px-10 lg:px-12">
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
