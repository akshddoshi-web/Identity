import { z } from "zod";
import { createPlannedLiftInputSchema, createPlannedMealInputSchema } from "@identity/shared";
import { calculateRecipeMacros } from "@identity/shared";
import { protectedProcedure, router } from "../trpc";

export const plannerRouter = router({
  createPlannedLift: protectedProcedure.input(createPlannedLiftInputSchema).mutation(async ({ ctx, input }) => {
    return ctx.prisma.plannedLift.create({ data: { ...input, userId: ctx.userId } });
  }),

  markLiftCompleted: protectedProcedure
    .input(z.object({ plannedLiftId: z.string(), workoutSessionId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      return ctx.prisma.plannedLift.update({
        where: { id: input.plannedLiftId, userId: ctx.userId },
        data: { status: "completed", workoutSessionId: input.workoutSessionId },
      });
    }),

  markLiftSkipped: protectedProcedure
    .input(z.object({ plannedLiftId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      return ctx.prisma.plannedLift.update({
        where: { id: input.plannedLiftId, userId: ctx.userId },
        data: { status: "skipped" },
      });
    }),

  createPlannedMeal: protectedProcedure.input(createPlannedMealInputSchema).mutation(async ({ ctx, input }) => {
    return ctx.prisma.plannedMeal.create({ data: { ...input, userId: ctx.userId } });
  }),

  /** One-tap "log the planned meal as eaten" — creates the real MealLogEntry and links it back. */
  logPlannedMeal: protectedProcedure
    .input(z.object({ plannedMealId: z.string(), loggedAt: z.coerce.date() }))
    .mutation(async ({ ctx, input }) => {
      const planned = await ctx.prisma.plannedMeal.findFirstOrThrow({
        where: { id: input.plannedMealId, userId: ctx.userId },
      });

      if (planned.foodId) {
        const food = await ctx.prisma.food.findUniqueOrThrow({ where: { id: planned.foodId } });
        const grams = planned.quantityGrams ?? 100;
        const factor = grams / 100;
        const entry = await ctx.prisma.mealLogEntry.create({
          data: {
            userId: ctx.userId,
            loggedAt: input.loggedAt,
            source: "food",
            foodId: food.id,
            quantityGrams: grams,
            calories: food.caloriesPer100g * factor,
            proteinG: food.proteinGPer100g * factor,
            carbsG: food.carbsGPer100g * factor,
            fatG: food.fatGPer100g * factor,
          },
        });
        return ctx.prisma.plannedMeal.update({ where: { id: planned.id }, data: { loggedEntryId: entry.id } });
      }

      if (planned.recipeId) {
        const recipe = await ctx.prisma.recipe.findUniqueOrThrow({
          where: { id: planned.recipeId },
          include: { ingredients: { include: { food: true } } },
        });
        const { perServing } = calculateRecipeMacros(
          recipe.ingredients.map((i) => ({
            grams: i.grams,
            per100g: {
              calories: i.food.caloriesPer100g,
              proteinG: i.food.proteinGPer100g,
              carbsG: i.food.carbsGPer100g,
              fatG: i.food.fatGPer100g,
            },
          })),
          recipe.servings,
        );
        const servings = planned.servings ?? 1;
        const entry = await ctx.prisma.mealLogEntry.create({
          data: {
            userId: ctx.userId,
            loggedAt: input.loggedAt,
            source: "recipe",
            recipeId: recipe.id,
            servings,
            calories: perServing.calories * servings,
            proteinG: perServing.proteinG * servings,
            carbsG: perServing.carbsG * servings,
            fatG: perServing.fatG * servings,
          },
        });
        return ctx.prisma.plannedMeal.update({ where: { id: planned.id }, data: { loggedEntryId: entry.id } });
      }

      throw new Error("Planned meal has neither a food nor a recipe attached");
    }),

  /** Aggregates all three planning tracks for a date range — the calendar view's main query. */
  weeklyView: protectedProcedure
    .input(z.object({ from: z.coerce.date(), to: z.coerce.date() }))
    .query(async ({ ctx, input }) => {
      const [lifts, meals, expenses] = await Promise.all([
        ctx.prisma.plannedLift.findMany({
          where: { userId: ctx.userId, scheduledDate: { gte: input.from, lte: input.to } },
        }),
        ctx.prisma.plannedMeal.findMany({
          where: { userId: ctx.userId, scheduledDate: { gte: input.from, lte: input.to } },
        }),
        ctx.prisma.plannedExpense.findMany({
          where: { userId: ctx.userId, dueDate: { gte: input.from, lte: input.to } },
        }),
      ]);

      const byDate = new Map<string, { lifts: typeof lifts; meals: typeof meals; expenses: typeof expenses }>();
      const dateKey = (d: Date) => d.toISOString().slice(0, 10);

      for (const lift of lifts) {
        const key = dateKey(lift.scheduledDate);
        if (!byDate.has(key)) byDate.set(key, { lifts: [], meals: [], expenses: [] });
        byDate.get(key)!.lifts.push(lift);
      }
      for (const meal of meals) {
        const key = dateKey(meal.scheduledDate);
        if (!byDate.has(key)) byDate.set(key, { lifts: [], meals: [], expenses: [] });
        byDate.get(key)!.meals.push(meal);
      }
      for (const expense of expenses) {
        const key = dateKey(expense.dueDate);
        if (!byDate.has(key)) byDate.set(key, { lifts: [], meals: [], expenses: [] });
        byDate.get(key)!.expenses.push(expense);
      }

      return Array.from(byDate.entries())
        .map(([date, tracks]) => ({ date, ...tracks }))
        .sort((a, b) => (a.date < b.date ? -1 : 1));
    }),
});
