import { clsx } from "@/lib/clsx";

interface Props {
  pct: number; // 0-100
  color: string;
  size?: "sm" | "md";
}

export function ProgressBar({ pct, color, size = "md" }: Props) {
  return (
    <div className={clsx("mt-1.5 overflow-hidden rounded-full bg-panel2", size === "sm" ? "h-[5px]" : "h-2")}>
      <div
        className="h-full"
        style={{ width: `${Math.min(Math.max(pct, 0), 100)}%`, background: color }}
      />
    </div>
  );
}
