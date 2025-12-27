import { motion } from "framer-motion";
import { NavLink } from "react-router-dom";

type NavItem = {
  label: string;
  icon: React.ComponentType<{ size?: number }>;
  path: string;
};

type SidebarProps = {
  items: NavItem[];
};

export function Sidebar({ items }: SidebarProps) {
  return (
    <aside className="w-64 border-r border-slate-800/70 p-6 space-y-10 bg-ink-950/80">
      <div>
        <p className="tag text-xs text-emerald-300">CLEAR PLATFORM</p>
        <h1 className="text-2xl font-semibold tracking-tight">Clear Analytics</h1>
        <p className="text-sm text-slate-400 mt-2">
          Markets • Risk • Global Tracking
        </p>
      </div>
      <nav className="space-y-2">
        {items.map(({ label, icon: Icon, path }) => (
          <NavLink key={label} to={path}>
            {({ isActive }) => (
              <motion.div
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left ${
                  isActive ? "bg-ink-700/70 text-white shadow-glow" : "text-slate-300 hover:bg-ink-700/40"
                }`}
                whileHover={{ x: 4 }}
                transition={{ type: "spring", stiffness: 120, damping: 12 }}
              >
                <Icon size={18} />
                <span className="text-sm">{label}</span>
              </motion.div>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="glass-panel rounded-2xl p-4 scanline">
        <p className="tag text-xs text-emerald-300">SYSTEM STATUS</p>
        <h3 className="text-lg font-semibold mt-2">Online</h3>
        <p className="text-sm text-slate-400 mt-1">Feeds monitored. Integrity checks active.</p>
      </div>
    </aside>
  );
}
