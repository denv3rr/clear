type ErrorBannerProps = {
  title?: string;
  messages: string[];
  onRetry?: () => void;
  retryLabel?: string;
};

export function ErrorBanner({
  title = "Data fetch issue",
  messages,
  onRetry,
  retryLabel = "Retry"
}: ErrorBannerProps) {
  if (!messages.length) return null;
  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-xs text-amber-200">
      <p className="text-amber-100 font-semibold">{title}</p>
      <div className="mt-2 space-y-1">
        {messages.map((message, idx) => (
          <p key={`${message}-${idx}`}>{message}</p>
        ))}
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-full border border-amber-400/40 px-3 py-1 text-[11px] text-amber-200"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}
