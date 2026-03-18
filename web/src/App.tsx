import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import Dashboard from "./pages/Dashboard";

const Clients = lazy(() => import("./pages/Clients"));
const Osint = lazy(() => import("./pages/Osint"));
const Reports = lazy(() => import("./pages/Reports"));
const System = lazy(() => import("./pages/System"));

function RouteLoading() {
  return (
    <div className="glass-panel rounded-2xl p-6">
      <p className="tag text-xs text-emerald-300">LOADING</p>
      <p className="mt-2 text-sm text-slate-300">Loading workspace...</p>
    </div>
  );
}

export default function App() {
  return (
    <AppShell>
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/osint" element={<Osint />} />
          <Route path="/trackers" element={<Navigate to="/osint?tab=trackers" replace />} />
          <Route path="/intel" element={<Navigate to="/osint?tab=intel" replace />} />
          <Route path="/news" element={<Navigate to="/osint?tab=news" replace />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/system" element={<System />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
