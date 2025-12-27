import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import Clients from "./pages/Clients";
import Dashboard from "./pages/Dashboard";
import Intel from "./pages/Intel";
import News from "./pages/News";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import Tools from "./pages/Tools";
import Trackers from "./pages/Trackers";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/clients" element={<Clients />} />
        <Route path="/trackers" element={<Trackers />} />
        <Route path="/intel" element={<Intel />} />
        <Route path="/news" element={<News />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/tools" element={<Tools />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
