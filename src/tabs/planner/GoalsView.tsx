import { usePlannerStore } from "@/store/usePlannerStore";
import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { clsx } from "@/lib/clsx";

export function GoalsView() {
  const goals = usePlannerStore((s) => s.goals);

  return (
    <div className="grid grid-cols-12 gap-3.5">
      <Card span={12} title="Long-term goals" hint="Broken into milestones so progress is visible, not just a deadline">
        {goals.map((g) => {
          const doneCt = g.milestones.filter((m) => m.done).length;
          return (
            <div key={g.id} className="mb-2.5 bg-panel3 p-3.5 last:mb-0">
              <div className="mb-2 flex items-center justify-between text-[13px] font-bold">
                <span>{g.name}</span>
                <span>
                  {doneCt}/{g.milestones.length} done · {g.deadline}
                </span>
              </div>
              <ProgressBar pct={(doneCt / g.milestones.length) * 100} color="var(--accent)" />
              <div className="mt-3.5 border-t border-border pt-3.5">
                {g.milestones.map((m) => (
                  <div
                    key={m.label}
                    className={clsx("flex items-center gap-2 py-1 text-xs text-sub", m.done && "text-accent")}
                  >
                    {m.done ? "✅" : "⬜"} {m.label}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </Card>
    </div>
  );
}
