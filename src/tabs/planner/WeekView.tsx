import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { usePlannerStore } from "@/store/usePlannerStore";
import { buildScheduleAlert } from "@/lib/plannerInsights";
import { WEEKDAYS, TODAY_WEEKDAY } from "@/lib/plannerDates";
import { PlannerBlockRow } from "./PlannerBlockRow";
import { WeekTimeGrid } from "./WeekTimeGrid";
import { Dot } from "@/components/ui/Dot";
import { Card } from "@/components/ui/Card";
import { clsx } from "@/lib/clsx";

export function WeekView() {
  const week = usePlannerStore((s) => s.week);
  const catColors = usePlannerStore((s) => s.catColors);
  const [mode, setMode] = useState<"list" | "grid">("list");
  const navigate = useNavigate();

  const alert = useMemo(() => buildScheduleAlert(week), [week]);
  const categories = Object.keys(catColors) as (keyof typeof catColors)[];

  return (
    <div className="grid grid-cols-12 gap-3.5">
      <Card span={12} title="This week" hint="Classes, clubs, work, and goals in one schedule">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-3.5 text-[11.5px]">
            {categories.map((c) => (
              <div key={c} className="flex items-center gap-1.5">
                <Dot color={catColors[c]} />
                {c}
              </div>
            ))}
          </div>
          <div className="flex border border-border">
            {(["list", "grid"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={clsx(
                  "px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wide",
                  mode === m ? "bg-text text-bg" : "text-sub hover:bg-panel3 hover:text-text",
                )}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {mode === "list" ? (
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
            {WEEKDAYS.map((day) => {
              const items = week[day];
              const doneCt = items.filter((i) => i.done).length;
              return (
                <div
                  key={day}
                  className={clsx(
                    "min-h-[150px] border border-border bg-panel2 p-3",
                    day === TODAY_WEEKDAY && "border-text",
                  )}
                >
                  <h4 className="mb-2 flex items-center justify-between font-mono text-[11px] uppercase tracking-wide text-sub">
                    {day}
                    <span>
                      {doneCt}/{items.length}
                    </span>
                  </h4>
                  {items.map((block) => (
                    <div key={block.id} className="mb-1.5 last:mb-0">
                      <PlannerBlockRow day={day} block={block} color={catColors[block.cat]} />
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        ) : (
          <WeekTimeGrid />
        )}
      </Card>

      <Card span={12} title="Completion accountability" hint="Same escalation logic as budget/calorie tracking, applied to your schedule">
        {alert ? (
          <div
            className={clsx(
              "flex gap-3 border border-border bg-panel3 p-3.5",
              alert.tone === "crit" ? "border-l-[3px] border-l-neg" : "border-l-[3px] border-l-warn",
            )}
          >
            <div className="mt-px text-lg leading-none">{alert.tone === "crit" ? "🔴" : "🟡"}</div>
            <div>
              <b className="mb-0.5 block text-[13px]">{alert.title}</b>
              <span className="text-xs leading-relaxed text-sub">{alert.body}</span>
            </div>
          </div>
        ) : (
          <div className="text-xs text-sub">You're on track.</div>
        )}
        <button
          onClick={() => navigate("/planner/week/plan-tomorrow")}
          className="mt-3.5 border border-border px-3.5 py-2 font-mono text-[11px] font-medium uppercase tracking-wide text-sub hover:bg-text hover:text-bg"
        >
          Plan tomorrow →
        </button>
      </Card>
    </div>
  );
}
