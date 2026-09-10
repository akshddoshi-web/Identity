import { z } from "zod";

export const macroProfileSchema = z.object({
  calories: z.number().nonnegative(),
  proteinG: z.number().nonnegative(),
  carbsG: z.number().nonnegative(),
  fatG: z.number().nonnegative(),
  fiberG: z.number().nonnegative().optional(),
  sugarG: z.number().nonnegative().optional(),
  sodiumMg: z.number().nonnegative().optional(),
});
export type MacroProfileInput = z.infer<typeof macroProfileSchema>;

export const foodSchema = z.object({
  id: z.string(),
  source: z.enum(["usda", "custom"]),
  externalId: z.string().nullable(),
  name: z.string().min(1),
  brand: z.string().nullable(),
  per100g: macroProfileSchema,
});
export type Food = z.infer<typeof foodSchema>;

export const recipeIngredientSchema = z.object({
  foodId: z.string(),
  grams: z.number().positive(),
});

export const recipeSchema = z.object({
  id: z.string(),
  userId: z.string(),
  name: z.string().min(1),
  servings: z.number().int().positive(),
  ingredients: z.array(recipeIngredientSchema).min(1),
});
export type Recipe = z.infer<typeof recipeSchema>;
export const createRecipeInputSchema = recipeSchema.omit({ id: true, userId: true });

export const mealLogEntrySchema = z.object({
  id: z.string(),
  userId: z.string(),
  loggedAt: z.coerce.date(),
  source: z.enum(["food", "recipe"]),
  foodId: z.string().nullable(),
  recipeId: z.string().nullable(),
  quantityGrams: z.number().positive().nullable(),
  servings: z.number().positive().nullable(),
  macros: macroProfileSchema,
});
export type MealLogEntry = z.infer<typeof mealLogEntrySchema>;

export const activityLevelSchema = z.enum([
  "sedentary",
  "lightly_active",
  "moderately_active",
  "very_active",
  "extremely_active",
]);

export const nutritionProfileSchema = z.object({
  userId: z.string(),
  sex: z.enum(["male", "female"]),
  weightKg: z.number().positive(),
  heightCm: z.number().positive(),
  age: z.number().int().positive(),
  activityLevel: activityLevelSchema,
  goal: z.enum(["lose", "maintain", "gain"]),
  manualCalorieTarget: z.number().int().positive().nullable(),
  macroSplit: z.object({
    proteinPercent: z.number(),
    carbsPercent: z.number(),
    fatPercent: z.number(),
  }),
});
export type NutritionProfile = z.infer<typeof nutritionProfileSchema>;

export const bodyWeightEntrySchema = z.object({
  id: z.string(),
  userId: z.string(),
  loggedAt: z.coerce.date(),
  weightKg: z.number().positive(),
});
export type BodyWeightEntry = z.infer<typeof bodyWeightEntrySchema>;
