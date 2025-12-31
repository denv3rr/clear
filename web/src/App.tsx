import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import Clients from "./pages/Clients";
import Dashboard from "./pages/Dashboard";
import Intel from "./pages/Intel";
import News from "./pages/News";
import Reports from "./pages/Reports";
import System from "./pages/System";
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
        <Route path="/system" element={<System />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
