import { useNavigate } from "react-router-dom";
import { usePlannerStore } from "@/store/usePlannerStore";
import { TODAY_WEEKDAY, TOMORROW_WEEKDAY } from "@/lib/plannerDates";
import { Dot } from "@/components/ui/Dot";
import { Pill } from "@/components/ui/Pill";

export function PlanTomorrowView() {
  const navigate = useNavigate();
  const week = usePlannerStore((s) => s.week);
  const catColors = usePlannerStore((s) => s.catColors);
  const moveBlockToTomorrow = usePlannerStore((s) => s.moveBlockToTomorrow);
  const dropBlock = usePlannerStore((s) => s.dropBlock);

  const unfinishedToday = week[TODAY_WEEKDAY].filter((b) => !b.done);
  const tomorrowPlan = week[TOMORROW_WEEKDAY];

  return (
    <div className="mx-auto max-w-rm">
      <span
        className="mb-2.5 inline-block cursor-pointer text-xs text-sub hover:text-text"
        onClick={() => navigate("/planner/week")}
      >
        ← Back to week
      </span>

      <h3 className="mb-0.5 text-lg font-bold">Plan tomorrow</h3>
      <div className="mb-6 text-xs text-sub">
        End-of-day ritual: everything left over from {TODAY_WEEKDAY} needs a real decision — move it to{" "}
        {TOMORROW_WEEKDAY}, or drop it. Nothing carries over silently.
      </div>

      <div className="mb-1.5 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">
        Unfinished today · {unfinishedToday.length}
      </div>

      {unfinishedToday.length === 0 ? (
        <div className="border border-border bg-panel3 p-4 text-xs text-sub">
          Everything's handled — nothing left to triage.
        </div>
      ) : (
        unfinishedToday.map((block) => (
          <div
            key={block.id}
            className="flex items-center justify-between gap-3 border-t border-border py-3 first:border-t-0"
          >
            <div className="flex items-center gap-2">
              <Dot color={catColors[block.cat]} />
              <span className="text-[13px]">{block.text}</span>
            </div>
            <div className="flex flex-shrink-0 gap-1.5">
              <Pill
                variant="primary"
                className="px-2.5 py-[3px] text-[10px]"
                onClick={() => moveBlockToTomorrow(TODAY_WEEKDAY, block.id, TOMORROW_WEEKDAY)}
              >
                → {TOMORROW_WEEKDAY}
              </Pill>
              <Pill className="px-2.5 py-[3px] text-[10px]" onClick={() => dropBlock(TODAY_WEEKDAY, block.id)}>
                Drop
              </Pill>
            </div>
          </div>
        ))
      )}

      <div className="mb-1.5 mt-9 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">
        Already on {TOMORROW_WEEKDAY} · {tomorrowPlan.length}
      </div>
      {tomorrowPlan.length === 0 ? (
        <div className="text-xs text-sub">Nothing planned yet.</div>
      ) : (
        tomorrowPlan.map((block) => (
          <div key={block.id} className="flex items-center gap-2 border-t border-border py-2.5 first:border-t-0">
            <Dot color={catColors[block.cat]} />
            <span className="text-[13px] text-sub">{block.text}</span>
          </div>
        ))
      )}
    </div>
  );
}
