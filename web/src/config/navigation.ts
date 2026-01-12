import {
  Eye,
  FileText,
  Settings,
  Shield,
  TerminalSquare
} from "lucide-react";

export const navItems = [
  { label: "Overview", icon: TerminalSquare, path: "/" },
  { label: "Clients", icon: Shield, path: "/clients" },
  { label: "OSINT", icon: Eye, path: "/osint" },
  { label: "Reports", icon: FileText, path: "/reports" },
  { label: "System", icon: Settings, path: "/system" }
];
