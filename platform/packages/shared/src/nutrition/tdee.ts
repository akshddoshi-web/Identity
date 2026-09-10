export type BiologicalSexForBmr = "male" | "female";

export interface MifflinStJeorInput {
  sex: BiologicalSexForBmr;
  weightKg: number;
  heightCm: number;
  age: number;
}

/** Mifflin-St Jeor BMR (kcal/day). The standard, more accurate successor to Harris-Benedict. */
export function calculateBmr({ sex, weightKg, heightCm, age }: MifflinStJeorInput): number {
  const base = 10 * weightKg + 6.25 * heightCm - 5 * age;
  return Math.round(sex === "male" ? base + 5 : base - 161);
}

export type ActivityLevel =
  | "sedentary"
  | "lightly_active"
  | "moderately_active"
  | "very_active"
  | "extremely_active";

export const ACTIVITY_MULTIPLIERS: Record<ActivityLevel, number> = {
  sedentary: 1.2,
  lightly_active: 1.375,
  moderately_active: 1.55,
  very_active: 1.725,
  extremely_active: 1.9,
};

export function calculateTdee(bmr: number, activityLevel: ActivityLevel): number {
  return Math.round(bmr * ACTIVITY_MULTIPLIERS[activityLevel]);
}

export type Goal = "lose" | "maintain" | "gain";

/** Conservative default surplus/deficit of ~500 kcal/day (~1 lb/week). */
export const DEFAULT_GOAL_ADJUSTMENT_KCAL = 500;

export function calculateCalorieTarget(
  tdee: number,
  goal: Goal,
  adjustmentKcal: number = DEFAULT_GOAL_ADJUSTMENT_KCAL,
): number {
  if (goal === "lose") return Math.round(tdee - adjustmentKcal);
  if (goal === "gain") return Math.round(tdee + adjustmentKcal);
  return Math.round(tdee);
}

export interface AutoTargetInput extends MifflinStJeorInput {
  activityLevel: ActivityLevel;
  goal: Goal;
  adjustmentKcal?: number;
}

export interface AutoTargetResult {
  bmr: number;
  tdee: number;
  calorieTarget: number;
}

/** Full pipeline: stats -> BMR -> TDEE -> goal-adjusted calorie target. */
export function calculateAutoCalorieTarget(input: AutoTargetInput): AutoTargetResult {
  const bmr = calculateBmr(input);
  const tdee = calculateTdee(bmr, input.activityLevel);
  const calorieTarget = calculateCalorieTarget(tdee, input.goal, input.adjustmentKcal);
  return { bmr, tdee, calorieTarget };
}
