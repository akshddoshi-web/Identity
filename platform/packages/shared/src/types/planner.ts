import { z } from "zod";

export const plannedLiftSchema = z.object({
  id: z.string(),
  userId: z.string(),
  scheduledDate: z.coerce.date(),
  templateId: z.string().nullable(),
  label: z.string().min(1),
  status: z.enum(["planned", "completed", "skipped"]),
  workoutSessionId: z.string().nullable(),
});
export type PlannedLift = z.infer<typeof plannedLiftSchema>;
export const createPlannedLiftInputSchema = plannedLiftSchema.omit({
  id: true,
  userId: true,
  status: true,
  workoutSessionId: true,
});

export const plannedMealSchema = z.object({
  id: z.string(),
  userId: z.string(),
  scheduledDate: z.coerce.date(),
  slot: z.enum(["breakfast", "lunch", "dinner", "snack"]),
  foodId: z.string().nullable(),
  recipeId: z.string().nullable(),
  quantityGrams: z.number().positive().nullable(),
  servings: z.number().positive().nullable(),
  loggedEntryId: z.string().nullable(),
});
export type PlannedMeal = z.infer<typeof plannedMealSchema>;
export const createPlannedMealInputSchema = plannedMealSchema.omit({
  id: true,
  userId: true,
  loggedEntryId: true,
});

/** One day's worth of the three planning tracks, for the weekly/monthly calendar view. */
export interface DailyPlan {
  date: string; // YYYY-MM-DD
  lifts: PlannedLift[];
  meals: PlannedMeal[];
  expenses: {
    id: string;
    description: string;
    amountCents: number;
    reconciledTransactionId: string | null;
  }[];
}
