import type { ButtonHTMLAttributes } from "react";
import { clsx } from "@/lib/clsx";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "on";
}

export function Pill({ variant = "default", className, ...rest }: Props) {
  return (
    <button
      className={clsx(
        "cursor-pointer border border-border px-3.5 py-[7px] font-mono text-[11px] font-medium uppercase tracking-wide hover:bg-text hover:text-bg disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-text",
        variant === "primary" && "border-text bg-text text-bg",
        variant === "on" && "border-text bg-text text-bg",
        variant === "default" && "bg-panel3 text-text",
        className,
      )}
      {...rest}
    />
  );
}
