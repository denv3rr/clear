import { motion } from "framer-motion";
import { ChevronDown } from "lucide-react";

type CollapsibleProps = {
  title: string;
  meta?: React.ReactNode;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  className?: string;
  mountWhenOpen?: boolean;
};

export function Collapsible({
  title,
  meta,
  open,
  onToggle,
  children,
  className = "",
  mountWhenOpen = false
}: CollapsibleProps) {
  const shouldRenderChildren = open || !mountWhenOpen;

  return (
    <div className={`glass-panel rounded-2xl ${className}`}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-5 py-4 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300"
      >
        <div>
          <p className="text-sm font-semibold text-slate-100">{title}</p>
          {meta ? <p className="text-xs text-emerald-300 mt-1">{meta}</p> : null}
        </div>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.25 }}
          className="text-emerald-300"
        >
          <ChevronDown size={18} />
        </motion.span>
      </button>
      <motion.div
        initial={false}
        animate={{
          height: open ? "auto" : 0,
          opacity: open ? 1 : 0
        }}
        transition={{ duration: 0.3, ease: "easeInOut" }}
        className="overflow-hidden"
      >
        {shouldRenderChildren ? <div className="px-5 pb-5">{children}</div> : null}
      </motion.div>
    </div>
  );
}
