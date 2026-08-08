import { lazy, Suspense, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Card } from "../ui/Card";
import { SectionHeader } from "../ui/SectionHeader";
import { useSceneController } from "../../lib/scene";

const loadTrackersPanel = () =>
  import("../../pages/Trackers").then((module) => ({
    default: module.TrackersPanel,
  }));
const loadIntelPage = () => import("../../pages/Intel");
const loadNewsPage = () => import("../../pages/News");

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
    label: "Signals",
    description: "Regional impact summaries and diagnostics.",
  },
  {
    id: "news",
    label: "News",
    description: "Filtered market and world news feeds.",
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

export function OsintWorkspace({ embedded = false }: { embedded?: boolean }) {
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
  const globeButtonLabel = isOpen ? "World Live" : "Open World";

  return (
    <div className={embedded ? "space-y-5 osint-workspace--embedded" : "space-y-5"}>
      <section className="osint-command">
        <div className="osint-command__header">
          <SectionHeader
            label="World"
            title="World Workspace"
            right={
              <div className="osint-command__status">
                <span>{activeLabel}</span>
                <button
                  type="button"
                  data-testid="osint-open-globe"
                  onClick={() => openScene(preferredScene)}
                  className="osint-command__globe-button"
                >
                  {globeButtonLabel}
                </button>
              </div>
            }
          />
        </div>
        <div className="osint-command__body">
          <div className="osint-command__tabs" role="tablist" aria-label="World workspace tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setTab(tab.id)}
                onMouseEnter={() => {
                  void TAB_PRELOADERS[tab.id]();
                }}
                onFocus={() => {
                  void TAB_PRELOADERS[tab.id]();
                }}
                className={[
                  "osint-command__tab",
                  activeTab === tab.id ? "osint-command__tab--active" : "",
                ].join(" ")}
              >
                <span>{tab.label}</span>
                <small>{tab.description}</small>
              </button>
            ))}
          </div>
        </div>
      </section>
      <Suspense fallback={<TabLoadingState tab={activeTab} />}>
        {activeTab === "trackers" ? <TrackersPanel /> : null}
        {activeTab === "intel" ? <Intel /> : null}
        {activeTab === "news" ? <News /> : null}
      </Suspense>
    </div>
  );
}
