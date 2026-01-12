import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { SectionHeader } from "../components/ui/SectionHeader";
import Intel from "./Intel";
import News from "./News";
import { TrackersPanel } from "./Trackers";

const tabs = [
  {
    id: "trackers",
    label: "Trackers",
    description: "Live aviation and maritime activity.",
  },
  {
    id: "intel",
    label: "Intel",
    description: "Regional impact summaries and diagnostics.",
  },
  {
    id: "news",
    label: "News",
    description: "Filtered market and OSINT news feeds.",
  },
] as const;

type OsintTab = (typeof tabs)[number]["id"];

export default function Osint() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = useMemo<OsintTab>(() => {
    const requested = (searchParams.get("tab") || "").toLowerCase();
    const found = tabs.find((tab) => tab.id === requested);
    return (found?.id || "trackers") as OsintTab;
  }, [searchParams]);

  const setTab = (tab: OsintTab) => {
    setSearchParams({ tab });
  };

  const activeLabel = tabs.find((tab) => tab.id === activeTab)?.label || "Trackers";

  return (
    <div className="space-y-5">
      <Card className="rounded-2xl p-5">
        <SectionHeader
          label="OSINT"
          title="Open-Source Intelligence"
          right={activeLabel}
        />
        <p className="mt-2 text-sm text-slate-400">
          Trackers are grouped here and only surface in reports when account tags
          make them relevant.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setTab(tab.id)}
              className={[
                "rounded-full border px-4 py-2 text-xs transition",
                activeTab === tab.id
                  ? "border-emerald-400/60 bg-emerald-400/10 text-emerald-200"
                  : "border-slate-700 text-slate-300 hover:border-emerald-400/50 hover:text-emerald-200",
              ].join(" ")}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          {tabs.find((tab) => tab.id === activeTab)?.description}
        </p>
      </Card>
      {activeTab === "trackers" ? <TrackersPanel /> : null}
      {activeTab === "intel" ? <Intel /> : null}
      {activeTab === "news" ? <News /> : null}
    </div>
  );
}
