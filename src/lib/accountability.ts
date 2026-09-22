// Generic accountability engine: pure functions that turn "actual vs. target"
// data into alerts. Nothing here knows about budgets specifically — Home
// wires it up for avenue spend today, and later stages can feed it fitness
// (macros, workout adherence) or planner (schedule completion) targets
// through the same evaluate() call.
import type { Avenue } from "@/types/domain";

export type TargetDirection = "ceiling" | "floor";
export type AlertTone = "crit" | "warn";

export interface AccountabilityTarget {
  /** Stable id of the thing being tracked (avenue id, macro id, task-list id, ...) */
  id: string;
  /** Human label, e.g. "Entertainment" or "Protein" */
  label: string;
  actual: number;
  target: number;
  /**
   * "ceiling" — actual should stay at or below target (a budget, a calorie cap).
   * "floor" — actual should stay at or above target (protein intake, task completion rate).
   */
  direction: TargetDirection;
}

export interface AccountabilityAlert {
  id: string;
  sourceId: string;
  tone: AlertTone;
  title: string;
  body: string;
  ratio: number;
}

export interface EvaluateThresholds {
  /** ratio beyond which the target counts as critically breached */
  critRatio: number;
  /** ratio beyond which the target counts as a soft warning */
  warnRatio: number;
}

const CEILING_DEFAULTS: EvaluateThresholds = { critRatio: 1.1, warnRatio: 0.9 };
const FLOOR_DEFAULTS: EvaluateThresholds = { critRatio: 0.6, warnRatio: 0.85 };

export function defaultThresholds(direction: TargetDirection): EvaluateThresholds {
  return direction === "ceiling" ? CEILING_DEFAULTS : FLOOR_DEFAULTS;
}

/**
 * Evaluate a single actual-vs-target reading and return its tone + ratio,
 * or null if it isn't worth flagging. Callers layer their own copy
 * (title/body) on top — this function only decides *whether* and *how bad*.
 */
export function evaluateTarget(
  t: AccountabilityTarget,
  thresholds: EvaluateThresholds = defaultThresholds(t.direction),
): { tone: AlertTone; ratio: number } | null {
  if (t.target === 0) return null;
  const ratio = t.actual / t.target;

  if (t.direction === "ceiling") {
    if (ratio > thresholds.critRatio) return { tone: "crit", ratio };
    if (ratio > thresholds.warnRatio) return { tone: "warn", ratio };
    return null;
  }

  // floor
  if (ratio < thresholds.critRatio) return { tone: "crit", ratio };
  if (ratio < thresholds.warnRatio) return { tone: "warn", ratio };
  return null;
}

function fmtMoney(n: number): string {
  return (n < 0 ? "-$" : "$") + Math.abs(n).toFixed(2).replace(/\.00$/, "");
}

/**
 * Budget-vs-actual alerts for Home's avenues. This is the one concrete
 * consumer of the engine today; it supplies the copy, the engine supplies
 * the crit/warn decision.
 */
export function buildAvenueAlerts(avenues: Avenue[]): AccountabilityAlert[] {
  const alerts: AccountabilityAlert[] = [];

  for (const avenue of avenues) {
    const target: AccountabilityTarget = {
      id: avenue.id,
      label: avenue.name,
      actual: avenue.spent,
      target: avenue.budget,
      direction: "ceiling",
    };
    const result = evaluateTarget(target);
    if (!result) continue;

    if (result.tone === "crit") {
      const overBy = avenue.spent - avenue.budget;
      alerts.push({
        id: `${avenue.id}-crit`,
        sourceId: avenue.id,
        tone: "crit",
        ratio: result.ratio,
        title: `${avenue.name} is ${Math.round((result.ratio - 1) * 100)}% over budget`,
        body: `You've spent ${fmtMoney(avenue.spent)} of a ${fmtMoney(avenue.budget)} budget. Recommendation: cut new ${avenue.name.toLowerCase()} spend for the rest of the week, or move ${fmtMoney(Math.round(overBy * 0.6))} out of a lower-priority avenue to cover it.`,
      });
    } else {
      alerts.push({
        id: `${avenue.id}-warn`,
        sourceId: avenue.id,
        tone: "warn",
        ratio: result.ratio,
        title: `${avenue.name} is close to its limit`,
        body: `${fmtMoney(avenue.budget - avenue.spent)} left with days remaining in the cycle. No action needed yet.`,
      });
    }
  }

  return alerts;
}
