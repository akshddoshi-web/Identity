import type { ReactNode } from "react";
import { clsx } from "@/lib/clsx";

interface Props {
  title?: string;
  hint?: string;
  span?: 3 | 4 | 5 | 6 | 7 | 8 | 9 | 12;
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}

const SPAN_CLASS: Record<number, string> = {
  3: "col-span-12 md:col-span-3",
  4: "col-span-12 md:col-span-4",
  5: "col-span-12 md:col-span-5",
  6: "col-span-12 md:col-span-6",
  7: "col-span-12 md:col-span-7",
  8: "col-span-12 md:col-span-8",
  9: "col-span-12 md:col-span-9",
  12: "col-span-12",
};

export function Card({ title, hint, span = 12, children, className, onClick }: Props) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        "border border-border bg-panel2 p-5",
        SPAN_CLASS[span],
        onClick && "cursor-pointer",
        className,
      )}
    >
      {title && <h3 className="m-0 mb-1 font-mono text-xs font-bold uppercase tracking-wide">{title}</h3>}
      {hint && <div className="mb-4 text-xs text-sub">{hint}</div>}
      {children}
    </div>
  );
}
