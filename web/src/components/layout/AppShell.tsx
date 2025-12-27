import { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { navItems } from "../../config/navigation";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen gridlines text-slate-100">
      <div className="flex">
        <Sidebar items={navItems} />
        <main className="flex-1 p-8 space-y-8">{children}</main>
      </div>
    </div>
  );
}
