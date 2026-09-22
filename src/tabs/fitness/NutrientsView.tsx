import { useFitnessStore } from "@/store/useFitnessStore";
import { clsx } from "@/lib/clsx";

export function NutrientsView() {
  const micronutrients = useFitnessStore((s) => s.micronutrients);

  return (
    <div className="mx-auto max-w-rm">
      <div className="mb-1.5 mt-0 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">
        Micronutrient breakdown — today vs. reference intake
      </div>
      <div className="grid grid-cols-1 border border-border sm:grid-cols-2">
        {micronutrients.map((n, i) => (
          <div
            key={n.name}
            className={clsx(
              "flex justify-between border-b border-border p-3.5",
              i % 2 === 0 && "sm:border-r",
            )}
          >
            <span>{n.name}</span>
            <span className="font-mono text-sub">
              {n.current} / {n.reference}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
