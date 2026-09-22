import { useHomeStore } from "@/store/useHomeStore";
import { Card } from "@/components/ui/Card";
import { Dot } from "@/components/ui/Dot";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { fmt } from "@/lib/format";
import { clsx } from "@/lib/clsx";

export function BudgetsView() {
  const avenues = useHomeStore((s) => s.avenues);

  return (
    <div className="grid grid-cols-12 gap-3.5">
      {avenues.map((a) => {
        const over = a.spent > a.budget;
        return (
          <Card key={a.id} span={6} hint="Monthly budget">
            <h3 className="m-0 mb-1 flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wide">
              <Dot color={a.color} />
              {a.name}
            </h3>
            <div className="mt-4 flex items-baseline justify-between">
              <span className={clsx("text-2xl font-extrabold", over && "text-neg")}>{fmt(a.spent)}</span>
              <span className="text-xs text-sub">of {fmt(a.budget)}</span>
            </div>
            <ProgressBar pct={(a.spent / a.budget) * 100} color={over ? "var(--red)" : a.color} />
            <div className="mt-3.5 border-t border-border pt-3.5">
              {a.sub.map((item) => (
                <div key={item.label} className="flex justify-between py-0.5 text-xs text-sub">
                  <span>{item.label}</span>
                  <span>{fmt(item.amount)}</span>
                </div>
              ))}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
