import type { ReactNode } from "react";
import { clsx } from "@/lib/clsx";

type Tone = "ok" | "warn" | "crit" | "neutral";

interface Props {
  tone: Tone;
  children: ReactNode;
}

const TONE_CLASS: Record<Tone, string> = {
  ok: "border-text text-text",
  warn: "border-warn text-warn",
  crit: "bg-neg text-bg border-neg",
  neutral: "border-border text-sub bg-panel3",
};

export function Badge({ tone, children }: Props) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 border px-2 py-[3px] font-mono text-[10px] font-bold uppercase tracking-wide",
        TONE_CLASS[tone],
      )}
    >
      {children}
    </span>
  );
}
