// Fitness's consumer of the accountability engine — same shape as
// buildAvenueAlerts() (Home) and the concentration check in
// stockInsights.ts (Stocks): build an AccountabilityTarget, call
// evaluateTarget(), attach copy. Nothing here reimplements threshold logic.
import { evaluateTarget, type AccountabilityAlert, type AccountabilityTarget } from "./accountability";
import { currentWeekCompletion } from "./liftStats";
import type { FitnessData } from "@/types/fitness";

function buildCalorieAlert(data: FitnessData): AccountabilityAlert | null {
  const net = data.macros.cal.cur - data.exerciseCal;
  const target: AccountabilityTarget = {
    id: "calories",
    label: "Calories",
    actual: net,
    target: data.macros.cal.goal,
    direction: "ceiling",
  };
  const result = evaluateTarget(target);
  if (!result) return null;

  const over = net - data.macros.cal.goal;
  return {
    id: "calories",
    sourceId: "calories",
    tone: result.tone,
    ratio: result.ratio,
    severity: result.severity,
    title:
      result.tone === "crit"
        ? `${Math.round(over)} kcal over goal today`
        : "Calories are close to today's goal",
    body:
      result.tone === "crit"
        ? `${net} net kcal (${data.macros.cal.cur} food − ${data.exerciseCal} exercise) against a ${data.macros.cal.goal} kcal goal. Consider a lighter dinner or an extra walk.`
        : `${data.macros.cal.goal - net} kcal of headroom left today. No action needed yet.`,
  };
}

function buildProteinAlert(data: FitnessData): AccountabilityAlert | null {
  const target: AccountabilityTarget = {
    id: "protein",
    label: "Protein",
    actual: data.macros.protein.cur,
    target: data.macros.protein.goal,
    direction: "floor",
  };
  const result = evaluateTarget(target);
  if (!result) return null;

  return {
    id: "protein",
    sourceId: "protein",
    tone: result.tone,
    ratio: result.ratio,
    severity: result.severity,
    title: "Protein is trending under target",
    body: `${data.macros.protein.cur}g of a ${data.macros.protein.goal}g goal today. Consider adding a shake or a higher-protein dinner.`,
  };
}

function buildWorkoutCompletionAlert(data: FitnessData): AccountabilityAlert | null {
  const week = currentWeekCompletion(data.lifts);
  if (!week) return null;

  const target: AccountabilityTarget = {
    id: "workout-completion",
    label: "Workout completion",
    actual: week.completedSlots,
    target: week.plannedSlots,
    direction: "floor",
  };
  const result = evaluateTarget(target);
  if (!result) return null;

  return {
    id: "workout-completion",
    sourceId: "workout-completion",
    tone: result.tone,
    ratio: result.ratio,
    severity: result.severity,
    title: `${week.completedSlots} of ${week.plannedSlots} planned training days this week`,
    body: `Push/Legs/Pull is the plan each week; ${week.plannedSlots - week.completedSlots} slot${week.plannedSlots - week.completedSlots === 1 ? "" : "s"} didn't get a full session. No penalty, just visibility.`,
  };
}

/** Every fitness alert the accountability engine currently flags. */
export function buildFitnessAlerts(data: FitnessData): AccountabilityAlert[] {
  return [buildCalorieAlert(data), buildProteinAlert(data), buildWorkoutCompletionAlert(data)].filter(
    (a): a is AccountabilityAlert => a !== null,
  );
}
