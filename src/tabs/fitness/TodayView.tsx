import { useMemo } from "react";
import { useFitnessStore } from "@/store/useFitnessStore";
import { buildFitnessAlerts } from "@/lib/fitnessInsights";
import { Ring } from "@/components/ui/Ring";
import { Dot } from "@/components/ui/Dot";
import { clsx } from "@/lib/clsx";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export function TodayView() {
  const macros = useFitnessStore((s) => s.macros);
  const exerciseCal = useFitnessStore((s) => s.exerciseCal);
  const mealsToday = useFitnessStore((s) => s.mealsToday);
  const split = useFitnessStore((s) => s.split);
  const loggingStreakDays = useFitnessStore((s) => s.loggingStreakDays);
  const fitnessData = useFitnessStore((s) => s);

  const alerts = useMemo(() => buildFitnessAlerts(fitnessData), [fitnessData]);

  const remaining = macros.cal.goal - macros.cal.cur + exerciseCal;
  const pP = macros.protein.cur * 4;
  const pC = macros.carbs.cur * 4;
  const pF = macros.fat.cur * 9;
  const pTot = pP + pC + pF;

  return (
    <div className="mx-auto max-w-rm">
      <div className="pb-2.5 pt-1.5 text-center">
        <div className="font-mono text-[11px] uppercase tracking-[2px] text-sub">Calories remaining</div>
        <div className="mt-2.5 flex flex-wrap items-center justify-center gap-0">
          <div className="px-4 text-center">
            <div className="font-mono text-[22px] font-extrabold">{macros.cal.goal}</div>
            <div className="mt-0.5 text-[10px] uppercase tracking-wide text-sub">Goal</div>
          </div>
          <div className="text-[22px] font-light text-sub">−</div>
          <div className="px-4 text-center">
            <div className="font-mono text-[22px] font-extrabold">{macros.cal.cur}</div>
            <div className="mt-0.5 text-[10px] uppercase tracking-wide text-sub">Food</div>
          </div>
          <div className="text-[22px] font-light text-sub">+</div>
          <div className="px-4 text-center">
            <div className="font-mono text-[22px] font-extrabold">{exerciseCal}</div>
            <div className="mt-0.5 text-[10px] uppercase tracking-wide text-sub">Exercise</div>
          </div>
          <div className="text-[22px] font-light text-sub">=</div>
          <Ring current={macros.cal.cur - exerciseCal} goal={macros.cal.goal} color="var(--text)" size={140} />
        </div>
        <div className="mt-0.5 text-[13px] text-sub">{remaining} kcal remaining today</div>
      </div>

      <div className="my-4 flex h-2.5 w-full overflow-hidden border border-border">
        <div style={{ width: `${(pP / pTot) * 100}%`, background: "var(--blue)" }} />
        <div style={{ width: `${(pC / pTot) * 100}%`, background: "var(--purple)" }} />
        <div style={{ width: `${(pF / pTot) * 100}%`, background: "var(--orange)" }} />
      </div>
      <div className="flex flex-wrap justify-center gap-5 text-[11.5px]">
        <div className="flex items-center gap-1.5">
          <Dot color="var(--blue)" size={8} />
          Protein {macros.protein.cur}g / {macros.protein.goal}g
        </div>
        <div className="flex items-center gap-1.5">
          <Dot color="var(--purple)" size={8} />
          Carbs {macros.carbs.cur}g / {macros.carbs.goal}g
        </div>
        <div className="flex items-center gap-1.5">
          <Dot color="var(--orange)" size={8} />
          Fat {macros.fat.cur}g / {macros.fat.goal}g
        </div>
      </div>
      <div className="mt-3.5 text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-panel2 px-2.5 py-1 text-[11.5px] font-semibold">
          🔥 {loggingStreakDays}-day logging streak
        </span>
      </div>

      {alerts.length > 0 && (
        <>
          <div className="mb-1.5 mt-9 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">Accountability</div>
          {alerts.map((a) => (
            <div
              key={a.id}
              className={clsx(
                "mb-2.5 flex gap-3 border border-border bg-panel3 p-3.5 last:mb-0",
                a.tone === "crit" ? "border-l-[3px] border-l-neg" : "border-l-[3px] border-l-warn",
              )}
            >
              <div className="mt-px text-lg leading-none">{a.tone === "crit" ? "🔴" : "🟡"}</div>
              <div>
                <b className="mb-0.5 block text-[13px]">{a.title}</b>
                <span className="text-xs leading-relaxed text-sub">{a.body}</span>
              </div>
            </div>
          ))}
        </>
      )}

      {mealsToday.map((m) => {
        const total = m.items.reduce((s, i) => s + i.kcal, 0);
        return (
          <div key={m.name}>
            <div className="mt-9 flex items-center justify-between border-b border-border pb-2">
              <b className="font-mono text-[13px] uppercase tracking-wide">
                {m.name} · {total} kcal
              </b>
              <span className="cursor-pointer border border-border px-2 py-0.5 font-mono text-[11px] text-sub">
                + Add
              </span>
            </div>
            {m.items.map((item) => (
              <div key={item.name} className="flex justify-between border-b border-dashed border-border py-2.5 text-[13px]">
                <span>{item.name}</span>
                <span className="font-mono text-[12px] text-sub">{item.kcal} kcal</span>
              </div>
            ))}
          </div>
        );
      })}

      <div className="my-9 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">Today's split</div>
      {DAYS.map((d) => (
        <div key={d} className="flex justify-between border-t border-border py-3.5 first:border-t-0">
          <span className="font-mono text-[11px] text-sub">{d.toUpperCase()}</span>
          <span>{split[d]}</span>
        </div>
      ))}
    </div>
  );
}
