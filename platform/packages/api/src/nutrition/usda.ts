/**
 * USDA FoodData Central — free, no-cost nutrition database, used for the
 * searchable food database. Get a free API key at
 * https://fdc.nal.usda.gov/api-key-signup.html (the demo key `DEMO_KEY`
 * works for local dev at a low rate limit).
 */
const USDA_BASE_URL = "https://api.nal.usda.gov/fdc/v1";

export interface UsdaFoodResult {
  externalId: string;
  name: string;
  brand: string | null;
  caloriesPer100g: number;
  proteinGPer100g: number;
  carbsGPer100g: number;
  fatGPer100g: number;
  fiberGPer100g: number | null;
  sugarGPer100g: number | null;
  sodiumMgPer100g: number | null;
}

const NUTRIENT_IDS = {
  calories: 1008,
  protein: 1003,
  carbs: 1005,
  fat: 1004,
  fiber: 1079,
  sugar: 2000,
  sodium: 1093,
} as const;

interface UsdaNutrient {
  nutrientId: number;
  value: number;
}

interface UsdaFoodItem {
  fdcId: number;
  description: string;
  brandName?: string;
  foodNutrients: UsdaNutrient[];
}

function nutrientValue(nutrients: UsdaNutrient[], id: number): number | null {
  const match = nutrients.find((n) => n.nutrientId === id);
  return match ? match.value : null;
}

function toResult(item: UsdaFoodItem): UsdaFoodResult {
  return {
    externalId: String(item.fdcId),
    name: item.description,
    brand: item.brandName ?? null,
    caloriesPer100g: nutrientValue(item.foodNutrients, NUTRIENT_IDS.calories) ?? 0,
    proteinGPer100g: nutrientValue(item.foodNutrients, NUTRIENT_IDS.protein) ?? 0,
    carbsGPer100g: nutrientValue(item.foodNutrients, NUTRIENT_IDS.carbs) ?? 0,
    fatGPer100g: nutrientValue(item.foodNutrients, NUTRIENT_IDS.fat) ?? 0,
    fiberGPer100g: nutrientValue(item.foodNutrients, NUTRIENT_IDS.fiber),
    sugarGPer100g: nutrientValue(item.foodNutrients, NUTRIENT_IDS.sugar),
    sodiumMgPer100g: nutrientValue(item.foodNutrients, NUTRIENT_IDS.sodium),
  };
}

export async function searchUsdaFoods(query: string): Promise<UsdaFoodResult[]> {
  const apiKey = process.env.USDA_API_KEY ?? "DEMO_KEY";
  const url = `${USDA_BASE_URL}/foods/search?query=${encodeURIComponent(query)}&pageSize=25&api_key=${apiKey}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`USDA search failed: ${res.status}`);
  const data = (await res.json()) as { foods: UsdaFoodItem[] };
  return data.foods.map(toResult);
}
