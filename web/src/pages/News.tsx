import { Card } from "../components/ui/Card";
import { SectionHeader } from "../components/ui/SectionHeader";
import { useApi } from "../lib/api";

type NewsItem = {
  title: string;
  source?: string;
  url?: string;
  published_ts?: number;
};

type NewsPayload = {
  items: NewsItem[];
  cached?: boolean;
  stale?: boolean;
};

export default function News() {
  const { data } = useApi<NewsPayload>("/api/intel/news?limit=25", { interval: 60000 });
  const items = data?.items ?? [];

  return (
    <Card className="rounded-2xl p-6">
      <SectionHeader label="NEWS" title="Market Signals" right={data?.stale ? "Stale" : "Live"} />
      <div className="mt-6 space-y-4 text-sm text-slate-300">
        {items.length === 0 ? (
          <p>No news items available.</p>
        ) : (
          items.map((item) => (
            <div key={`${item.title}-${item.source}`} className="border-b border-slate-900/60 pb-3">
              <p className="text-slate-100 font-medium">{item.title}</p>
              <p className="text-xs text-slate-400">{item.source || "Unknown source"}</p>
              {item.url && (
                <a className="text-xs text-emerald-300" href={item.url} target="_blank" rel="noreferrer">
                  Open source
                </a>
              )}
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
