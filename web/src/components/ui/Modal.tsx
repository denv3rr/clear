import { useEffect } from "react";
import type { ReactNode } from "react";

type ModalProps = {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
};

export function Modal({
  open,
  title,
  description,
  onClose,
  children,
  footer
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700/70 bg-slate-950 shadow-xl">
        <div className="border-b border-slate-800 px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-slate-100">{title}</p>
              {description ? (
                <p className="mt-1 text-xs text-slate-400">{description}</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-slate-700/70 px-2 py-1 text-[11px] text-slate-300 hover:border-slate-500"
              aria-label="Close modal"
            >
              Close
            </button>
          </div>
        </div>
        <div className="px-5 py-4 text-sm text-slate-200">{children}</div>
        {footer ? (
          <div className="flex items-center justify-end gap-2 border-t border-slate-800 px-5 py-4">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
