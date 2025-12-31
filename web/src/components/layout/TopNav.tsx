import { useState } from "react";
import { NavLink } from "react-router-dom";
import { Menu, X, Bot } from "lucide-react";

type NavItem = {
  label: string;
  icon: React.ComponentType<{ size?: number }>;
  path: string;
};

type TopNavProps = {
  items: NavItem[];
  onToggleContext?: () => void;
  onToggleAssistant?: () => void;
};

export function TopNav({ items, onToggleContext, onToggleAssistant }: TopNavProps) {
  const utilityPaths = new Set(["/system"]);
  const primaryItems = items.filter((item) => !utilityPaths.has(item.path));
  const utilityItems = items.filter((item) => utilityPaths.has(item.path));
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="border-b border-slate-900/80 bg-ink-950/95 backdrop-blur">
      <div className="flex min-w-0 items-center gap-6 py-4 pl-6 pr-6 md:pl-10 md:pr-10 lg:pl-[68px] lg:pr-12">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label="Toggle navigation"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((prev) => !prev)}
            className="lg:hidden rounded-full border border-slate-800/80 p-2 text-slate-300 hover:border-slate-700 hover:text-white"
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
          <span className="text-lg font-semibold tracking-tight">[ CLEAR ]</span>
          <span className="hidden text-xs text-slate-500 sm:inline">
            Markets • Risk • Trackers
          </span>
        </div>
        <nav className="hidden lg:flex flex-1 min-w-0">
          <div className="flex gap-2 py-1">
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
          <div className="hidden lg:flex items-center gap-2">
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
            className="hidden lg:inline-flex rounded-full border border-slate-800/80 px-4 py-2 text-xs text-slate-300 hover:border-slate-700 hover:text-white"
            type="button"
            onClick={onToggleAssistant}
          >
            <Bot size={15} className="mr-2" />
            Assistant
          </button>
          <button
            className="hidden lg:inline-flex rounded-full border border-slate-800/80 px-4 py-2 text-xs text-slate-300 hover:border-slate-700 hover:text-white"
            type="button"
            onClick={onToggleContext}
          >
            Context
          </button>
        </div>
      </div>
      {mobileOpen ? (
        <div className="lg:hidden border-t border-slate-900/70 bg-ink-950/95">
          <div className="px-6 py-4 space-y-4">
            <nav className="space-y-2">
              {primaryItems.map(({ label, icon: Icon, path }) => (
                <NavLink
                  key={label}
                  to={path}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-2 rounded-xl px-4 py-2 text-sm transition",
                      isActive
                        ? "bg-slate-900/80 text-white"
                        : "text-slate-300 hover:bg-slate-900/50"
                    ].join(" ")
                  }
                >
                  <Icon size={16} />
                  <span>{label}</span>
                </NavLink>
              ))}
            </nav>
            <div className="border-t border-slate-900/70 pt-3 space-y-2">
              {utilityItems.map(({ label, icon: Icon, path }) => (
                <NavLink
                  key={label}
                  to={path}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-2 rounded-xl px-4 py-2 text-sm transition",
                      isActive
                        ? "bg-slate-900/80 text-white"
                        : "text-slate-300 hover:bg-slate-900/50"
                    ].join(" ")
                  }
                >
                  <Icon size={16} />
                  <span>{label}</span>
                </NavLink>
              ))}
              <button
                className="w-full rounded-xl border border-slate-800/80 px-4 py-2 text-left text-sm text-slate-300 hover:border-slate-700 hover:text-white"
                type="button"
                onClick={() => {
                  onToggleAssistant?.();
                  setMobileOpen(false);
                }}
              >
                Assistant
              </button>
              <button
                className="w-full rounded-xl border border-slate-800/80 px-4 py-2 text-left text-sm text-slate-300 hover:border-slate-700 hover:text-white"
                type="button"
                onClick={() => {
                  onToggleContext?.();
                  setMobileOpen(false);
                }}
              >
                Context
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </header>
  );
}
