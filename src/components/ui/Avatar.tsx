import { colorForLabel, initials } from "@/lib/format";
import { clsx } from "@/lib/clsx";

interface Props {
  label: string;
  size?: number;
  shape?: "circle" | "square";
}

export function Avatar({ label, size = 36, shape = "circle" }: Props) {
  const color = colorForLabel(label);
  return (
    <div
      className={clsx(
        "flex flex-shrink-0 items-center justify-center border border-border font-mono text-xs font-bold",
        shape === "circle" ? "rounded-full" : "rounded-none",
      )}
      style={{ width: size, height: size, background: "var(--panel3)", color }}
    >
      {initials(label)}
    </div>
  );
}
