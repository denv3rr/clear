import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import Clients from "./pages/Clients";
import Dashboard from "./pages/Dashboard";
import Osint from "./pages/Osint";
import Reports from "./pages/Reports";
import System from "./pages/System";

export default function App() {
  return (
    <AppShell>
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
    </AppShell>
  );
}
