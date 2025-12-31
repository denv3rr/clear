import {
  Activity,
  FileText,
  Newspaper,
  Plane,
  Settings,
  Shield,
  TerminalSquare
} from "lucide-react";

export const navItems = [
  { label: "Overview", icon: TerminalSquare, path: "/" },
  { label: "Clients", icon: Shield, path: "/clients" },
  { label: "Trackers", icon: Plane, path: "/trackers" },
  { label: "Intel", icon: Activity, path: "/intel" },
  { label: "News", icon: Newspaper, path: "/news" },
  { label: "Reports", icon: FileText, path: "/reports" },
  { label: "System", icon: Settings, path: "/system" }
];
