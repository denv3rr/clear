import { ReactNode, useState } from "react";
import { useLocation } from "react-router-dom";
import { navItems } from "../../config/navigation";
import { ErrorBanner } from "../ui/ErrorBanner";
import { getApiBase, useApi } from "../../lib/api";
import { ContextDrawer } from "./ContextDrawer";
import { ChatDrawer } from "../ui/ChatDrawer";
import { TopNav } from "./TopNav";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const { error: healthError, warnings: healthWarnings, refresh } = useApi<{
    status: string;
  }>(
    "/api/health",
    { interval: 60000 }
  );
  const [contextOpen, setContextOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const apiBase = getApiBase();
  const entry = (() => {
    const path = location.pathname;
    if (path === "/") return "dashboard";
    if (path.startsWith("/clients")) return "clients";
    if (path.startsWith("/reports")) return "reports";
    if (path.startsWith("/system")) return "system";
    if (path.startsWith("/osint")) return "osint";
    if (path.startsWith("/trackers")) return "trackers";
    if (path.startsWith("/intel")) return "intel";
    if (path.startsWith("/news")) return "news";
    return "unknown";
  })();
  const healthMessages: string[] = [];
  if (healthError) {
    healthMessages.push(`API health check failed (${apiBase}): ${healthError}`);
  }
  for (const warning of healthWarnings) {
    healthMessages.push(`API health warning: ${warning}`);
  }

  return (
    <div className="min-h-screen text-slate-100 overflow-x-hidden bg-black">
      <TopNav
        items={navItems}
        onToggleContext={() => setContextOpen((prev) => !prev)}
        onToggleAssistant={() => setAssistantOpen((prev) => !prev)}
      />
      <div className="flex min-h-screen min-w-0">
        <main className="flex-1 min-w-0 px-6 py-8 md:px-10 lg:px-12 space-y-10 overflow-x-hidden">
          <ErrorBanner messages={healthMessages} onRetry={refresh} />
          {children}
        </main>
      </div>
      {contextOpen ? (
        <ContextDrawer variant="overlay" onClose={() => setContextOpen(false)} />
      ) : null}
      {assistantOpen ? (
        <ChatDrawer entry={entry} onClose={() => setAssistantOpen(false)} />
      ) : null}
    </div>
  );
}
