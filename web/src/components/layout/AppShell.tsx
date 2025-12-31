import { ReactNode, useState } from "react";
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
  const { error: healthError, warnings: healthWarnings, refresh } = useApi<{
    status: string;
  }>(
    "/api/health",
    { interval: 60000 }
  );
  const [contextOpen, setContextOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const apiBase = getApiBase();
  const healthMessages: string[] = [];
  if (healthError) {
    healthMessages.push(`API health check failed (${apiBase}): ${healthError}`);
  }
  for (const warning of healthWarnings) {
    healthMessages.push(`API health warning: ${warning}`);
  }

  return (
    <div className="min-h-screen text-slate-100 overflow-x-hidden">
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
        <ChatDrawer onClose={() => setAssistantOpen(false)} />
      ) : null}
    </div>
  );
}
