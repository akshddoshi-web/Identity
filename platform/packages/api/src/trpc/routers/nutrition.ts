import { z } from "zod";
import {
  calculateAutoCalorieTarget,
  calculateRecipeMacros,
  createRecipeInputSchema,
  macroProfileSchema,
  nutritionProfileSchema,
  sumDailyMacros,
} from "@identity/shared";
import { searchUsdaFoods } from "../../nutrition/usda";
import { protectedProcedure, publicProcedure, router } from "../trpc";

export const nutritionRouter = router({
  searchFoods: publicProcedure.input(z.object({ query: z.string().min(1) })).query(async ({ ctx, input }) => {
    const [usdaResults, customFoods] = await Promise.all([
      searchUsdaFoods(input.query).catch(() => []),
      ctx.prisma.food.findMany({
        where: { source: "custom", name: { contains: input.query, mode: "insensitive" } },
        take: 25,
      }),
    ]);
    return { usdaResults, customFoods };
  }),

  importUsdaFood: protectedProcedure
    .input(
      z.object({
        externalId: z.string(),
        name: z.string(),
        brand: z.string().nullable(),
        caloriesPer100g: z.number(),
        proteinGPer100g: z.number(),
        carbsGPer100g: z.number(),
        fatGPer100g: z.number(),
        fiberGPer100g: z.number().nullable(),
        sugarGPer100g: z.number().nullable(),
        sodiumMgPer100g: z.number().nullable(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      return ctx.prisma.food.upsert({
        where: { source_externalId: { source: "usda", externalId: input.externalId } },
        create: { source: "usda", ...input },
        update: input,
      });
    }),

  createCustomFood: protectedProcedure
    .input(
      z.object({
        name: z.string().min(1),
        brand: z.string().optional(),
        per100g: macroProfileSchema,
      }),
    )
    .mutation(async ({ ctx, input }) => {
      return ctx.prisma.food.create({
        data: {
          source: "custom",
          name: input.name,
          brand: input.brand,
          createdByUserId: ctx.userId,
          caloriesPer100g: input.per100g.calories,
          proteinGPer100g: input.per100g.proteinG,
          carbsGPer100g: input.per100g.carbsG,
          fatGPer100g: input.per100g.fatG,
          fiberGPer100g: input.per100g.fiberG,
          sugarGPer100g: input.per100g.sugarG,
          sodiumMgPer100g: input.per100g.sodiumMg,
        },
      });
    }),

  createRecipe: protectedProcedure.input(createRecipeInputSchema).mutation(async ({ ctx, input }) => {
    const foods = await ctx.prisma.food.findMany({
      where: { id: { in: input.ingredients.map((i) => i.foodId) } },
    });
    const foodById = new Map(foods.map((f) => [f.id, f]));

    const { total, perServing } = calculateRecipeMacros(
      input.ingredients.map((i) => {
        const food = foodById.get(i.foodId);
        if (!food) throw new Error(`Food ${i.foodId} not found`);
        return {
          grams: i.grams,
          per100g: {
            calories: food.caloriesPer100g,
            proteinG: food.proteinGPer100g,
            carbsG: food.carbsGPer100g,
            fatG: food.fatGPer100g,
            fiberG: food.fiberGPer100g ?? undefined,
            sugarG: food.sugarGPer100g ?? undefined,
            sodiumMg: food.sodiumMgPer100g ?? undefined,
          },
        };
      }),
      input.servings,
    );

    const recipe = await ctx.prisma.recipe.create({
      data: {
        userId: ctx.userId,
        name: input.name,
        servings: input.servings,
        ingredients: { create: input.ingredients.map((i) => ({ foodId: i.foodId, grams: i.grams })) },
      },
      include: { ingredients: true },
    });

    return { recipe, macros: { total, perServing } };
  }),

  listRecipes: protectedProcedure.query(async ({ ctx }) => {
    return ctx.prisma.recipe.findMany({
      where: { userId: ctx.userId },
      include: { ingredients: { include: { food: true } } },
    });
  }),

  logMeal: protectedProcedure
    .input(
      z.object({
        loggedAt: z.coerce.date(),
        foodId: z.string().optional(),
        recipeId: z.string().optional(),
        quantityGrams: z.number().positive().optional(),
        servings: z.number().positive().optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      if (input.foodId) {
        const food = await ctx.prisma.food.findUniqueOrThrow({ where: { id: input.foodId } });
        const grams = input.quantityGrams ?? 100;
        const factor = grams / 100;
        return ctx.prisma.mealLogEntry.create({
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
            fiberG: food.fiberGPer100g ? food.fiberGPer100g * factor : null,
            sugarG: food.sugarGPer100g ? food.sugarGPer100g * factor : null,
            sodiumMg: food.sodiumMgPer100g ? food.sodiumMgPer100g * factor : null,
          },
        });
      }

      if (input.recipeId) {
        const recipe = await ctx.prisma.recipe.findUniqueOrThrow({
          where: { id: input.recipeId },
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
              fiberG: i.food.fiberGPer100g ?? undefined,
              sugarG: i.food.sugarGPer100g ?? undefined,
              sodiumMg: i.food.sodiumMgPer100g ?? undefined,
            },
          })),
          recipe.servings,
        );
        const servings = input.servings ?? 1;
        return ctx.prisma.mealLogEntry.create({
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
            fiberG: perServing.fiberG ? perServing.fiberG * servings : null,
            sugarG: perServing.sugarG ? perServing.sugarG * servings : null,
            sodiumMg: perServing.sodiumMg ? perServing.sodiumMg * servings : null,
          },
        });
      }

      throw new Error("Either foodId or recipeId must be provided");
    }),

  dailySummary: protectedProcedure.input(z.object({ date: z.coerce.date() })).query(async ({ ctx, input }) => {
    const dayStart = new Date(input.date);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = new Date(dayStart);
    dayEnd.setDate(dayEnd.getDate() + 1);

    const entries = await ctx.prisma.mealLogEntry.findMany({
      where: { userId: ctx.userId, loggedAt: { gte: dayStart, lt: dayEnd } },
    });
    const totals = sumDailyMacros(
      entries.map((e) => ({
        macros: {
          calories: e.calories,
          proteinG: e.proteinG,
          carbsG: e.carbsG,
          fatG: e.fatG,
          fiberG: e.fiberG ?? undefined,
          sugarG: e.sugarG ?? undefined,
          sodiumMg: e.sodiumMg ?? undefined,
        },
      })),
    );
    const profile = await ctx.prisma.nutritionProfile.findUnique({ where: { userId: ctx.userId } });

    return { entries, totals, targets: profile ? deriveTargets(profile) : null };
  }),

  getProfile: protectedProcedure.query(async ({ ctx }) => {
    return ctx.prisma.nutritionProfile.findUnique({ where: { userId: ctx.userId } });
  }),

  upsertProfile: protectedProcedure
    .input(nutritionProfileSchema.omit({ userId: true }))
    .mutation(async ({ ctx, input }) => {
      const data = {
        sex: input.sex,
        weightKg: input.weightKg,
        heightCm: input.heightCm,
        age: input.age,
        activityLevel: input.activityLevel,
        goal: input.goal,
        manualCalorieTarget: input.manualCalorieTarget,
        proteinPercent: input.macroSplit.proteinPercent,
        carbsPercent: input.macroSplit.carbsPercent,
        fatPercent: input.macroSplit.fatPercent,
      };
      return ctx.prisma.nutritionProfile.upsert({
        where: { userId: ctx.userId },
        create: { userId: ctx.userId, ...data },
        update: data,
      });
    }),

  logBodyWeight: protectedProcedure
    .input(z.object({ loggedAt: z.coerce.date(), weightKg: z.number().positive() }))
    .mutation(async ({ ctx, input }) => {
      return ctx.prisma.bodyWeightEntry.create({ data: { userId: ctx.userId, ...input } });
    }),

  bodyWeightHistory: protectedProcedure.query(async ({ ctx }) => {
    return ctx.prisma.bodyWeightEntry.findMany({
      where: { userId: ctx.userId },
      orderBy: { loggedAt: "asc" },
    });
  }),
});

function deriveTargets(profile: {
  manualCalorieTarget: number | null;
  sex: string;
  weightKg: number;
  heightCm: number;
  age: number;
  activityLevel: Parameters<typeof calculateAutoCalorieTarget>[0]["activityLevel"];
  goal: Parameters<typeof calculateAutoCalorieTarget>[0]["goal"];
  proteinPercent: number;
  carbsPercent: number;
  fatPercent: number;
}) {
  const calorieTarget =
    profile.manualCalorieTarget ??
    calculateAutoCalorieTarget({
      sex: profile.sex as "male" | "female",
      weightKg: profile.weightKg,
      heightCm: profile.heightCm,
      age: profile.age,
      activityLevel: profile.activityLevel,
      goal: profile.goal,
    }).calorieTarget;

  return {
    calories: calorieTarget,
    proteinG: Math.round((calorieTarget * (profile.proteinPercent / 100)) / 4),
    carbsG: Math.round((calorieTarget * (profile.carbsPercent / 100)) / 4),
    fatG: Math.round((calorieTarget * (profile.fatPercent / 100)) / 9),
  };
}
