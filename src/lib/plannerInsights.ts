// Planner's consumer of the accountability engine — fifth so far, same
// shape as buildAvenueAlerts (Home), the concentration check
// (stockInsights.ts), and calorie/protein/workout (fitnessInsights.ts).
// The prototype already computed this exact check inline in its Week view
// ("Same escalation logic as budget/calorie tracking, applied to your
// schedule") without actually routing it through the shared engine —
// this is that wiring, done for real.
import { evaluateTarget, type AccountabilityAlert, type AccountabilityTarget } from "./accountability";
import { pctS } from "./format";
import type { WeekPlan } from "@/types/planner";

// The prototype's own thresholds (rate<0.5 crit, rate<0.8 warn) — passed
// explicitly since they differ from evaluateTarget's floor defaults
// (0.6/0.85), the same way stockInsights.ts overrides its own ratios.
const SCHEDULE_THRESHOLDS = { critRatio: 0.5, warnRatio: 0.8 };

export function buildScheduleAlert(week: WeekPlan): AccountabilityAlert | null {
  const all = Object.values(week).flat();
  if (all.length === 0) return null;
  const done = all.filter((b) => b.done).length;

  const target: AccountabilityTarget = {
    id: "schedule",
    label: "Schedule",
    actual: done,
    target: all.length,
    direction: "floor",
  };
  const result = evaluateTarget(target, SCHEDULE_THRESHOLDS);
  if (!result) return null;

  const rate = done / all.length;
  return {
    id: "schedule",
    sourceId: "schedule",
    tone: result.tone,
    ratio: result.ratio,
    title: `Completion rate is ${pctS(rate)} this week`,
    body:
      result.tone === "crit"
        ? "Recommendation: cut this week's list to your top 3 items and reschedule the rest."
        : "On pace but a few things are slipping.",
  };
}
