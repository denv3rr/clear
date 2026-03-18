import { lazy, Suspense, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useSceneController } from "../lib/scene";

const loadTrackersPanel = () =>
  import("./Trackers").then((module) => ({
    default: module.TrackersPanel,
  }));
const loadIntelPage = () => import("./Intel");
const loadNewsPage = () => import("./News");

const TrackersPanel = lazy(loadTrackersPanel);
const Intel = lazy(loadIntelPage);
const News = lazy(loadNewsPage);

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

const TAB_PRELOADERS: Record<OsintTab, () => Promise<unknown>> = {
  trackers: loadTrackersPanel,
  intel: loadIntelPage,
  news: loadNewsPage,
};

function TabLoadingState({ tab }: { tab: OsintTab }) {
  return (
    <Card className="rounded-2xl p-5">
      <p className="tag text-xs text-emerald-300">LOADING</p>
      <p className="mt-2 text-sm text-slate-300">
        Loading {tab === "trackers" ? "tracker" : tab} workspace...
      </p>
    </Card>
  );
}

export default function Osint() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { isOpen, openScene } = useSceneController();
  const activeTab = useMemo<OsintTab>(() => {
    const requested = (searchParams.get("tab") || "").toLowerCase();
    const found = tabs.find((tab) => tab.id === requested);
    return (found?.id || "trackers") as OsintTab;
  }, [searchParams]);

  const setTab = (tab: OsintTab) => {
    setSearchParams({ tab });
  };

  const activeLabel = tabs.find((tab) => tab.id === activeTab)?.label || "Trackers";
  const preferredScene = "overview";
  const globeCallout =
    activeTab === "trackers"
      ? "Open the overview globe to move from list-and-card review into the fused world view. Tracker-only mode is still available inside the overlay, but the default launch now keeps regional conflict, weather, news, and emotion layers on the same canvas."
      : activeTab === "intel"
        ? "Open the overview globe to pivot into a regional risk view while keeping live tracker activity on the same canvas."
        : "Open the overview globe to combine live trackers, hotspots, and regional emotion/news pressure on one world canvas.";
  const globeButtonLabel = isOpen ? "Globe Live" : "Open Overview Globe";

  return (
    <div className="space-y-5">
      <Card className="rounded-2xl p-5">
        <SectionHeader
          label="OSINT"
          title="Open-Source Intelligence"
          right={
            <div className="flex items-center gap-3">
              <span>{activeLabel}</span>
              <button
                type="button"
                data-testid="osint-open-globe"
                onClick={() => openScene(preferredScene)}
                className="rounded-full border border-emerald-400/40 bg-emerald-400/10 px-3 py-1 text-[11px] text-emerald-200 hover:border-emerald-300 hover:text-emerald-100"
              >
                {globeButtonLabel}
              </button>
            </div>
          }
        />
        <p className="mt-2 text-sm text-slate-400">
          Trackers are grouped here and only surface in reports when account tags
          make them relevant.
        </p>
        <div className="mt-3 rounded-2xl border border-emerald-400/15 bg-emerald-400/5 px-4 py-3 text-xs text-slate-300">
          {globeCallout}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setTab(tab.id)}
              onMouseEnter={() => {
                void TAB_PRELOADERS[tab.id]();
              }}
              onFocus={() => {
                void TAB_PRELOADERS[tab.id]();
              }}
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
      <Suspense fallback={<TabLoadingState tab={activeTab} />}>
        {activeTab === "trackers" ? <TrackersPanel /> : null}
        {activeTab === "intel" ? <Intel /> : null}
        {activeTab === "news" ? <News /> : null}
      </Suspense>
    </div>
  );
}
