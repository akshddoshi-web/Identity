import { useHomeStore } from "@/store/useHomeStore";
import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { fmt, pctS } from "@/lib/format";

export function GoalsView() {
  const savingsGoals = useHomeStore((s) => s.savingsGoals);

  return (
    <div className="grid grid-cols-12 gap-3.5">
      <Card span={12} title="Savings goals" hint="Auto-funded from your Savings avenue">
        {savingsGoals.map((g) => {
          const p = Math.min((g.current / g.target) * 100, 100);
          return (
            <div key={g.id} className="mb-2.5 bg-panel3 p-3.5 last:mb-0">
              <div className="mb-2 flex items-center justify-between text-[13px] font-bold">
                <span>{g.name}</span>
                <span>
                  {fmt(g.current)} / {fmt(g.target)}
                </span>
              </div>
              <ProgressBar pct={p} color="var(--accent)" />
              <div className="mt-1.5 text-[11.5px] text-sub">
                Target: {g.deadline} · {pctS(g.current / g.target)} funded
              </div>
            </div>
          );
        })}
      </Card>
    </div>
  );
}
