import { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { navItems } from "../../config/navigation";
import { ErrorBanner } from "../ui/ErrorBanner";
import { getApiBase, useApi } from "../../lib/api";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const { error: healthError, refresh } = useApi<{ status: string }>(
    "/api/health",
    { interval: 60000 }
  );
  const apiBase = getApiBase();
  const healthMessage = healthError
    ? `API health check failed (${apiBase}): ${healthError}`
    : null;

  return (
    <div className="min-h-screen gridlines text-slate-100">
      <div className="flex">
        <Sidebar items={navItems} />
        <main className="flex-1 p-8 space-y-8">
          <ErrorBanner
            messages={healthMessage ? [healthMessage] : []}
            onRetry={refresh}
          />
          {children}
        </main>
      </div>
    </div>
  );
}
