/** Macro values are grams unless noted; calories are kcal. Stored per-100g for ingredients. */
export interface MacroProfile {
  calories: number;
  proteinG: number;
  carbsG: number;
  fatG: number;
  fiberG?: number;
  sugarG?: number;
  sodiumMg?: number;
}

export const CALORIES_PER_GRAM = {
  protein: 4,
  carbs: 4,
  fat: 9,
  alcohol: 7,
} as const;

/** Atwater estimate — used to sanity-check/backfill calories when a food source omits them. */
export function estimateCaloriesFromMacros(macros: {
  proteinG: number;
  carbsG: number;
  fatG: number;
}): number {
  return (
    macros.proteinG * CALORIES_PER_GRAM.protein +
    macros.carbsG * CALORIES_PER_GRAM.carbs +
    macros.fatG * CALORIES_PER_GRAM.fat
  );
}

export interface IngredientAmount {
  /** Macro profile per 100g of this ingredient, as stored in the food database. */
  per100g: MacroProfile;
  grams: number;
}

function scaleMacroProfile(per100g: MacroProfile, grams: number): MacroProfile {
  const factor = grams / 100;
  const scaled: MacroProfile = {
    calories: per100g.calories * factor,
    proteinG: per100g.proteinG * factor,
    carbsG: per100g.carbsG * factor,
    fatG: per100g.fatG * factor,
  };
  if (per100g.fiberG !== undefined) scaled.fiberG = per100g.fiberG * factor;
  if (per100g.sugarG !== undefined) scaled.sugarG = per100g.sugarG * factor;
  if (per100g.sodiumMg !== undefined) scaled.sodiumMg = per100g.sodiumMg * factor;
  return scaled;
}

function sumMacroProfiles(profiles: MacroProfile[]): MacroProfile {
  const total: MacroProfile = { calories: 0, proteinG: 0, carbsG: 0, fatG: 0 };
  let fiber = 0,
    sugar = 0,
    sodium = 0;
  let hasFiber = false,
    hasSugar = false,
    hasSodium = false;

  for (const p of profiles) {
    total.calories += p.calories;
    total.proteinG += p.proteinG;
    total.carbsG += p.carbsG;
    total.fatG += p.fatG;
    if (p.fiberG !== undefined) {
      fiber += p.fiberG;
      hasFiber = true;
    }
    if (p.sugarG !== undefined) {
      sugar += p.sugarG;
      hasSugar = true;
    }
    if (p.sodiumMg !== undefined) {
      sodium += p.sodiumMg;
      hasSodium = true;
    }
  }
  if (hasFiber) total.fiberG = fiber;
  if (hasSugar) total.sugarG = sugar;
  if (hasSodium) total.sodiumMg = sodium;
  return total;
}

function roundMacroProfile(profile: MacroProfile, decimals = 1): MacroProfile {
  const r = (n: number) => Number(n.toFixed(decimals));
  const rounded: MacroProfile = {
    calories: Math.round(profile.calories),
    proteinG: r(profile.proteinG),
    carbsG: r(profile.carbsG),
    fatG: r(profile.fatG),
  };
  if (profile.fiberG !== undefined) rounded.fiberG = r(profile.fiberG);
  if (profile.sugarG !== undefined) rounded.sugarG = r(profile.sugarG);
  if (profile.sodiumMg !== undefined) rounded.sodiumMg = Math.round(profile.sodiumMg);
  return rounded;
}

/**
 * Ingredient-level recipe calculator: given raw ingredients (each with a
 * per-100g macro profile and a quantity in grams), computes total recipe
 * macros and a per-serving breakdown.
 */
export function calculateRecipeMacros(
  ingredients: IngredientAmount[],
  servings: number,
): { total: MacroProfile; perServing: MacroProfile } {
  if (servings <= 0) throw new Error("servings must be > 0");
  const scaledProfiles = ingredients.map((i) => scaleMacroProfile(i.per100g, i.grams));
  const rawTotal = sumMacroProfiles(scaledProfiles);
  return {
    total: roundMacroProfile(rawTotal),
    perServing: roundMacroProfile(scaleMacroProfileByServings(rawTotal, servings)),
  };
}

function scaleMacroProfileByServings(total: MacroProfile, servings: number): MacroProfile {
  const factor = 1 / servings;
  const scaled: MacroProfile = {
    calories: total.calories * factor,
    proteinG: total.proteinG * factor,
    carbsG: total.carbsG * factor,
    fatG: total.fatG * factor,
  };
  if (total.fiberG !== undefined) scaled.fiberG = total.fiberG * factor;
  if (total.sugarG !== undefined) scaled.sugarG = total.sugarG * factor;
  if (total.sodiumMg !== undefined) scaled.sodiumMg = total.sodiumMg * factor;
  return scaled;
}

export interface DailyLogEntry {
  macros: MacroProfile;
}

/** Rolls up any number of logged meals/foods for a day (or week) into totals. */
export function sumDailyMacros(entries: DailyLogEntry[]): MacroProfile {
  return roundMacroProfile(sumMacroProfiles(entries.map((e) => e.macros)));
}

export interface MacroTargets {
  calories: number;
  proteinG: number;
  carbsG: number;
  fatG: number;
}

export interface MacroSplit {
  proteinPercent: number;
  carbsPercent: number;
  fatPercent: number;
}

/** Converts a calorie target + macro % split (e.g. 30/40/30) into gram targets. */
export function macroTargetsFromSplit(calorieTarget: number, split: MacroSplit): MacroTargets {
  const total = split.proteinPercent + split.carbsPercent + split.fatPercent;
  if (Math.round(total) !== 100) {
    throw new Error(`macro split must sum to 100%, got ${total}%`);
  }
  return {
    calories: Math.round(calorieTarget),
    proteinG: Math.round((calorieTarget * (split.proteinPercent / 100)) / CALORIES_PER_GRAM.protein),
    carbsG: Math.round((calorieTarget * (split.carbsPercent / 100)) / CALORIES_PER_GRAM.carbs),
    fatG: Math.round((calorieTarget * (split.fatPercent / 100)) / CALORIES_PER_GRAM.fat),
  };
}
