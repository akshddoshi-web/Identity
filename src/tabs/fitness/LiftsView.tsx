import { useNavigate } from "react-router-dom";
import { useFitnessStore } from "@/store/useFitnessStore";
import { bestSetEver, lastSessionSummary, trendOverSessions } from "@/lib/liftStats";
import { clsx } from "@/lib/clsx";

export function LiftsView() {
  const lifts = useFitnessStore((s) => s.lifts);
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-rm">
      <div className="mb-1.5 mt-0 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">
        Lift progress — tap a lift for the full log
      </div>
      {lifts.map((lift) => {
        const last = lastSessionSummary(lift.sessions);
        const pr = bestSetEver(lift.sessions);
        const trend = trendOverSessions(lift.sessions);
        return (
          <div
            key={lift.id}
            onClick={() => navigate(`/fitness/lifts/${lift.id}`)}
            className="flex cursor-pointer items-center justify-between border-t border-border py-4 first:border-t-0 hover:bg-panel3"
          >
            <div>
              <div className="text-[13px] font-semibold">{lift.name}</div>
              <div className="text-[11.5px] text-sub">
                {last?.weight} lb × {last?.reps} · PR {pr?.weight} lb × {pr?.reps}
              </div>
            </div>
            {trend && (
              <div className={clsx("text-xs font-bold", trend.up ? "text-pos" : "text-sub")}>
                {trend.up ? "▲" : "—"} {trend.label}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
