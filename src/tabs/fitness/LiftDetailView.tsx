import { useNavigate } from "react-router-dom";
import { useFitnessStore } from "@/store/useFitnessStore";
import { Sparkline } from "@/components/ui/Sparkline";
import {
  bestSetEver,
  lastSessionSummary,
  sparklineWeights,
  trendOverSessions,
  windowedSessions,
} from "@/lib/liftStats";

interface Props {
  liftId: string;
}

export function LiftDetailView({ liftId }: Props) {
  const navigate = useNavigate();
  const lifts = useFitnessStore((s) => s.lifts);
  const lift = lifts.find((l) => l.id === liftId);

  if (!lift) {
    return (
      <div className="mx-auto max-w-rm py-16 text-center text-xs text-sub">
        Couldn't find that lift.{" "}
        <button className="underline" onClick={() => navigate("/fitness/lifts")}>
          ← Back to list
        </button>
      </div>
    );
  }

  const pr = bestSetEver(lift.sessions);
  const last = lastSessionSummary(lift.sessions);
  const trend = trendOverSessions(lift.sessions);
  const weights = sparklineWeights(lift.sessions);
  const sessions = [...windowedSessions(lift.sessions)].reverse(); // newest first, log style

  return (
    <div className="mx-auto max-w-rm">
      <span
        className="mb-2.5 inline-block cursor-pointer text-xs text-sub hover:text-text"
        onClick={() => navigate("/fitness/lifts")}
      >
        ← Back to list
      </span>

      <h3 className="mb-0.5 text-lg font-bold">{lift.name}</h3>
      <div className="mb-4 text-xs text-sub">
        {lift.muscleGroup} · {lift.slot} day · Personal record: {pr?.weight} lb × {pr?.reps}
      </div>

      <Sparkline data={weights} color={trend?.up ? "var(--accent)" : "var(--sub)"} width={560} height={90} />

      <div className="mt-3.5 text-[13px]">
        Last logged: <b>{last?.weight} lb × {last?.reps}</b>
        {trend && (
          <>
            {" "}
            · Trend: <span className={trend.up ? "text-pos" : ""}>{trend.label}</span>
          </>
        )}
      </div>

      <div className="my-9 font-mono text-[11px] uppercase tracking-[1.5px] text-sub">
        Workout log — {sessions.length} sessions, newest first
      </div>
      {sessions.map((session) => {
        const volume = session.sets.reduce((s, set) => s + set.weight * set.reps, 0);
        return (
          <div key={session.date} className="mb-3.5 border border-border bg-panel3 last:mb-0">
            <div className="flex items-center justify-between border-b border-border px-3.5 py-2.5">
              <b className="text-[12.5px]">{session.date}</b>
              <span className="font-mono text-[11px] text-sub">{volume.toLocaleString()} lb volume</span>
            </div>
            {session.sets.map((set, i) => (
              <div
                key={i}
                className="flex items-center justify-between px-3.5 py-2 text-[12.5px]"
                style={{ borderTop: i > 0 ? "1px dashed var(--border)" : undefined }}
              >
                <span className="w-14 font-mono text-[10.5px] uppercase tracking-wide text-sub">Set {i + 1}</span>
                <span className="flex-1 font-semibold">
                  {set.weight} lb × {set.reps}
                </span>
                {set.rpe !== undefined && <span className="font-mono text-[11px] text-sub">RPE {set.rpe}</span>}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
