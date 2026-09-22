import { useMemo } from "react";
import { useFitnessStore } from "@/store/useFitnessStore";
import { Sparkline } from "@/components/ui/Sparkline";
import { BarChart } from "@/components/ui/BarChart";
import {
  bestSetEver,
  detectWorkingSetPRs,
  streakMilestones,
  weeklyVolumeByMuscleGroup,
} from "@/lib/liftStats";
import { clsx } from "@/lib/clsx";

interface HistoryEntry {
  date: string;
  label: string;
  tone: "pr" | "streak" | "broken";
}

export function ProgressView() {
  const lifts = useFitnessStore((s) => s.lifts);
  const bodyweightHistory = useFitnessStore((s) => s.bodyweightHistory);

  const volumeByGroup = useMemo(() => {
    const rows = weeklyVolumeByMuscleGroup(lifts);
    const groups = new Map<string, { label: string; value: number }[]>();
    for (const r of rows) {
      const arr = groups.get(r.group) ?? [];
      arr.push({ label: `W${r.weekIndex + 1}`, value: r.volume });
      groups.set(r.group, arr);
    }
    return groups;
  }, [lifts]);

  const history = useMemo<HistoryEntry[]>(() => {
    const prEvents = lifts.flatMap((l) =>
      detectWorkingSetPRs(l.sessions).map((e) => ({
        date: e.date,
        label: `New working-set best — ${l.name}: ${e.weight} lb × ${e.reps}`,
        tone: "pr" as const,
      })),
    );
    const streakEvents = streakMilestones(lifts).map((e) => ({
      date: e.date,
      label: e.label,
      tone: e.kind === "streak" ? ("streak" as const) : ("broken" as const),
    }));
    return [...prEvents, ...streakEvents].sort((a, b) => (a.date < b.date ? 1 : -1));
  }, [lifts]);

  return (
    <div className="grid grid-cols-12 gap-3.5">
      <div className="col-span-12 border border-border bg-panel2 p-5 md:col-span-6">
        <h3 className="m-0 mb-1 font-mono text-xs font-bold uppercase tracking-wide">Bodyweight trend</h3>
        <div className="mb-4 text-xs text-sub">Last {bodyweightHistory.length} check-ins, lbs</div>
        <Sparkline data={bodyweightHistory.map((b) => b.weight)} color="var(--blue)" width={480} height={90} />
        <div className="mt-2 text-xs text-sub">
          {bodyweightHistory[0].weight} → {bodyweightHistory[bodyweightHistory.length - 1].weight} lbs
        </div>
      </div>

      <div className="col-span-12 border border-border bg-panel2 p-5 md:col-span-6">
        <h3 className="m-0 mb-4 font-mono text-xs font-bold uppercase tracking-wide">Personal records</h3>
        <table className="w-full text-[13px]">
          <thead>
            <tr>
              <th className="pb-2 text-left text-[11px] uppercase tracking-wide text-sub">Lift</th>
              <th className="pb-2 text-left text-[11px] uppercase tracking-wide text-sub">PR</th>
            </tr>
          </thead>
          <tbody>
            {lifts.map((l) => {
              const pr = bestSetEver(l.sessions);
              return (
                <tr key={l.id} className="border-t border-border">
                  <td className="py-2">{l.name}</td>
                  <td className="py-2">
                    {pr?.weight} lb × {pr?.reps}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="col-span-12 border border-border bg-panel2 p-5">
        <h3 className="m-0 mb-1 font-mono text-xs font-bold uppercase tracking-wide">Weekly training volume by muscle group</h3>
        <div className="mb-4 text-xs text-sub">Sum of weight × reps per week, derived from the set-by-set log</div>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          {[...volumeByGroup.entries()].map(([group, points]) => (
            <div key={group}>
              <div className="mb-1.5 text-[12px] font-semibold">{group}</div>
              <BarChart data={points} color="var(--blue)" width={340} height={100} />
            </div>
          ))}
        </div>
      </div>

      <div className="col-span-12 border border-border bg-panel2 p-5">
        <h3 className="m-0 mb-1 font-mono text-xs font-bold uppercase tracking-wide">Personal history</h3>
        <div className="mb-4 text-xs text-sub">
          PRs and training-split streaks, computed from your logged sets — not a social feed
        </div>
        {history.length === 0 ? (
          <div className="text-xs text-sub">Nothing recorded yet.</div>
        ) : (
          history.map((h, i) => (
            <div key={i} className="flex gap-3 border-t border-border py-3 first:border-t-0">
              <span className="w-24 flex-shrink-0 font-mono text-[11px] text-sub">{h.date}</span>
              <span
                className={clsx(
                  "text-[13px]",
                  h.tone === "pr" && "text-pos",
                  h.tone === "broken" && "text-sub",
                )}
              >
                {h.label}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
