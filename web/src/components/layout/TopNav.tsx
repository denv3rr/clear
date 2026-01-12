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
    <header className="border-b border-slate-700 bg-slate-950/95 backdrop-blur">
      <div className="flex min-w-0 items-center gap-6 py-4 pl-6 pr-6 md:pl-10 md:pr-10 min-[1800px]:pl-[68px] min-[1800px]:pr-12">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label="Toggle navigation"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((prev) => !prev)}
            className="min-[1800px]:hidden rounded-full border border-slate-700 p-2 text-slate-100 hover:border-green-500 hover:text-green-500"
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
          <span className="text-lg font-semibold tracking-tight">[ CLEAR ]</span>
          <span className="hidden text-xs text-slate-500 md:inline">
            Markets • Risk • OSINT
          </span>
        </div>
        <nav className="hidden min-[1800px]:flex flex-1 min-w-0">
          <div className="flex gap-2 py-1">
            {primaryItems.map(({ label, icon: Icon, path }) => (
              <NavLink
                key={label}
                to={path}
                className={({ isActive }) =>
                  [
                    "flex items-center gap-2 rounded-full px-4 py-2 text-sm transition",
                    isActive
                      ? "bg-slate-800 text-green-500"
                      : "text-slate-300 hover:bg-slate-800"
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
            <div className="hidden min-[1800px]:flex items-center gap-2">
            {utilityItems.map(({ label, icon: Icon, path }) => (
              <NavLink
                key={label}
                to={path}
                className={({ isActive }) =>
                  [
                    "flex items-center gap-2 rounded-full px-3 py-2 text-xs transition",
                    isActive
                      ? "bg-slate-800 text-green-500"
                      : "text-slate-300 hover:bg-slate-800"
                  ].join(" ")
                }
              >
                <Icon size={15} />
                <span className="whitespace-nowrap">{label}</span>
              </NavLink>
            ))}
          </div>
          <button
            className="hidden min-[1800px]:inline-flex rounded-full border border-slate-700 px-4 py-2 text-xs text-slate-100 hover:border-green-500 hover:text-green-500"
            type="button"
            onClick={onToggleAssistant}
          >
            <Bot size={15} className="mr-2" />
            Assistant
          </button>
          <button
            className="hidden min-[1800px]:inline-flex rounded-full border border-slate-700 px-4 py-2 text-xs text-slate-100 hover:border-green-500 hover:text-green-500"
            type="button"
            onClick={onToggleContext}
          >
            Context
          </button>
        </div>
      </div>
      {mobileOpen ? (
        <div className="min-[1800px]:hidden border-t border-slate-700 bg-slate-950/95">
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
                        ? "bg-slate-800 text-green-500"
                        : "text-slate-300 hover:bg-slate-800"
                    ].join(" ")
                  }
                >
                  <Icon size={16} />
                  <span>{label}</span>
                </NavLink>
              ))}
            </nav>
            <div className="border-t border-slate-700 pt-3 space-y-2">
              {utilityItems.map(({ label, icon: Icon, path }) => (
                <NavLink
                  key={label}
                  to={path}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-2 rounded-xl px-4 py-2 text-sm transition",
                      isActive
                        ? "bg-slate-800 text-green-500"
                        : "text-slate-300 hover:bg-slate-800"
                    ].join(" ")
                  }
                >
                  <Icon size={16} />
                  <span>{label}</span>
                </NavLink>
              ))}
              <button
                className="w-full rounded-xl border border-slate-700 px-4 py-2 text-left text-sm text-slate-100 hover:border-green-500 hover:text-green-500"
                type="button"
                onClick={() => {
                  onToggleAssistant?.();
                  setMobileOpen(false);
                }}
              >
                Assistant
              </button>
              <button
                className="w-full rounded-xl border border-slate-700 px-4 py-2 text-left text-sm text-slate-100 hover:border-green-500 hover:text-green-500"
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
