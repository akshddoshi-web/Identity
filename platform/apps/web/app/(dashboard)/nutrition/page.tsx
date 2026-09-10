"use client";

import { useState } from "react";
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { StatCard } from "@/components/StatCard";
import { trpc } from "@/lib/trpc/client";

function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

export default function NutritionPage() {
  const utils = trpc.useUtils();
  const dailySummary = trpc.nutrition.dailySummary.useQuery({ date: startOfToday() });
  const profile = trpc.nutrition.getProfile.useQuery();
  const recipes = trpc.nutrition.listRecipes.useQuery();
  const bodyWeight = trpc.nutrition.bodyWeightHistory.useQuery();

  const [query, setQuery] = useState("");
  const search = trpc.nutrition.searchFoods.useQuery({ query }, { enabled: query.length > 1 });

  const importAndLog = trpc.nutrition.importUsdaFood.useMutation();
  const logMeal = trpc.nutrition.logMeal.useMutation({
    onSuccess: () => utils.nutrition.dailySummary.invalidate(),
  });

  const [recipeName, setRecipeName] = useState("");
  const [recipeServings, setRecipeServings] = useState("1");
  const [recipeIngredients, setRecipeIngredients] = useState<{ foodId: string; name: string; grams: string }[]>([]);
  const [lastRecipeMacros, setLastRecipeMacros] = useState<{ calories: number; proteinG: number; carbsG: number; fatG: number } | null>(null);
  const createRecipe = trpc.nutrition.createRecipe.useMutation({
    onSuccess: (result) => {
      setLastRecipeMacros(result.macros.perServing);
      setRecipeName("");
      setRecipeIngredients([]);
      utils.nutrition.listRecipes.invalidate();
    },
  });

  const [profileForm, setProfileForm] = useState({
    sex: "male" as "male" | "female",
    weightKg: "80",
    heightCm: "180",
    age: "30",
    activityLevel: "moderately_active" as const,
    goal: "maintain" as const,
  });
  const upsertProfile = trpc.nutrition.upsertProfile.useMutation({
    onSuccess: () => utils.nutrition.getProfile.invalidate(),
  });

  const [weightInput, setWeightInput] = useState("");
  const logWeight = trpc.nutrition.logBodyWeight.useMutation({
    onSuccess: () => {
      utils.nutrition.bodyWeightHistory.invalidate();
      setWeightInput("");
    },
  });

  const totals = dailySummary.data?.totals;
  const targets = dailySummary.data?.targets;

  async function addUsdaFoodToRecipe(result: {
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
  }) {
    const food = await importAndLog.mutateAsync(result);
    setRecipeIngredients((ings) => [...ings, { foodId: food.id, name: food.name, grams: "100" }]);
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl">Nutrition</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatCard label="Calories" value={totals ? `${Math.round(totals.calories)}` : "—"} sublabel={targets ? `of ${targets.calories}` : undefined} accent="ember" />
        <StatCard label="Protein" value={totals ? `${Math.round(totals.proteinG)}g` : "—"} sublabel={targets ? `of ${targets.proteinG}g` : undefined} accent="jade" />
        <StatCard label="Carbs" value={totals ? `${Math.round(totals.carbsG)}g` : "—"} sublabel={targets ? `of ${targets.carbsG}g` : undefined} accent="gold" />
        <StatCard label="Fat" value={totals ? `${Math.round(totals.fatG)}g` : "—"} sublabel={targets ? `of ${targets.fatG}g` : undefined} />
      </div>

      <section className="panel space-y-3 p-5">
        <h2 className="text-lg">Log a food</h2>
        <input
          className="input"
          placeholder="Search USDA foods (e.g. 'chicken breast')..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {search.data?.usdaResults.map((result) => (
            <div key={result.externalId} className="flex items-center justify-between rounded-lg px-2 py-1 text-sm hover:bg-ink-800">
              <span>
                {result.name} <span className="text-ink-500">({Math.round(result.caloriesPer100g)} kcal/100g)</span>
              </span>
              <button
                className="btn-secondary px-2 py-1 text-xs"
                onClick={async () => {
                  const food = await importAndLog.mutateAsync(result);
                  logMeal.mutate({ loggedAt: new Date(), foodId: food.id, quantityGrams: 100 });
                }}
              >
                Log 100g
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="panel space-y-3 p-5">
        <h2 className="text-lg">Ingredient-level recipe builder</h2>
        <p className="text-xs text-ink-500">
          Search a food above's results won't add to a recipe directly — use this search to build a
          custom recipe from raw ingredients; macros are computed automatically per serving.
        </p>
        <input
          className="input"
          placeholder="Search an ingredient to add..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query.length > 1 && (
          <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-ink-800 p-2">
            {search.data?.usdaResults.map((result) => (
              <button
                key={result.externalId}
                className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-ink-800"
                onClick={() => addUsdaFoodToRecipe(result)}
              >
                {result.name}
              </button>
            ))}
          </div>
        )}

        <input className="input" placeholder="Recipe name" value={recipeName} onChange={(e) => setRecipeName(e.target.value)} />

        {recipeIngredients.map((ing, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="flex-1 text-sm text-ink-200">{ing.name}</span>
            <input
              type="number"
              className="input w-24"
              value={ing.grams}
              onChange={(e) =>
                setRecipeIngredients((ings) => ings.map((x, idx) => (idx === i ? { ...x, grams: e.target.value } : x)))
              }
            />
            <span className="text-xs text-ink-500">g</span>
          </div>
        ))}

        <div className="flex items-center gap-2">
          <label className="text-sm text-ink-400">Servings</label>
          <input type="number" min="1" className="input w-20" value={recipeServings} onChange={(e) => setRecipeServings(e.target.value)} />
          <button
            className="btn-primary"
            disabled={recipeIngredients.length === 0 || !recipeName || createRecipe.isPending}
            onClick={() =>
              createRecipe.mutate({
                name: recipeName,
                servings: Number(recipeServings),
                ingredients: recipeIngredients.map((i) => ({ foodId: i.foodId, grams: Number(i.grams) })),
              })
            }
          >
            Save recipe
          </button>
        </div>

        {lastRecipeMacros && (
          <p className="text-sm text-jade-400">
            Per serving: {Math.round(lastRecipeMacros.calories)} kcal · {Math.round(lastRecipeMacros.proteinG)}p /{" "}
            {Math.round(lastRecipeMacros.carbsG)}c / {Math.round(lastRecipeMacros.fatG)}f
          </p>
        )}

        <div className="divide-y divide-ink-800 pt-2">
          {recipes.data?.map((recipe) => (
            <div key={recipe.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                {recipe.name} <span className="text-ink-500">({recipe.servings} servings)</span>
              </span>
              <button
                className="btn-secondary px-2 py-1 text-xs"
                onClick={() => logMeal.mutate({ loggedAt: new Date(), recipeId: recipe.id, servings: 1 })}
              >
                Log 1 serving
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="panel space-y-3 p-5">
        <h2 className="text-lg">Targets (auto-calculated from your stats)</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <select className="input" value={profileForm.sex} onChange={(e) => setProfileForm((f) => ({ ...f, sex: e.target.value as "male" | "female" }))}>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
          <input className="input" type="number" placeholder="Weight (kg)" value={profileForm.weightKg} onChange={(e) => setProfileForm((f) => ({ ...f, weightKg: e.target.value }))} />
          <input className="input" type="number" placeholder="Height (cm)" value={profileForm.heightCm} onChange={(e) => setProfileForm((f) => ({ ...f, heightCm: e.target.value }))} />
          <input className="input" type="number" placeholder="Age" value={profileForm.age} onChange={(e) => setProfileForm((f) => ({ ...f, age: e.target.value }))} />
          <button
            className="btn-primary"
            onClick={() =>
              upsertProfile.mutate({
                sex: profileForm.sex,
                weightKg: Number(profileForm.weightKg),
                heightCm: Number(profileForm.heightCm),
                age: Number(profileForm.age),
                activityLevel: profileForm.activityLevel,
                goal: profileForm.goal,
                manualCalorieTarget: null,
                macroSplit: { proteinPercent: 30, carbsPercent: 40, fatPercent: 30 },
              })
            }
          >
            Save
          </button>
        </div>
        {profile.data && <p className="text-xs text-ink-500">Current goal: {profile.data.goal}, activity: {profile.data.activityLevel}</p>}
      </section>

      <section className="panel space-y-3 p-5">
        <h2 className="text-lg">Body weight</h2>
        <div className="flex gap-2">
          <input className="input w-32" type="number" placeholder="kg" value={weightInput} onChange={(e) => setWeightInput(e.target.value)} />
          <button className="btn-secondary" onClick={() => logWeight.mutate({ loggedAt: new Date(), weightKg: Number(weightInput) })}>
            Log weight
          </button>
        </div>
        {bodyWeight.data && bodyWeight.data.length > 1 && (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={bodyWeight.data.map((e) => ({ date: new Date(e.loggedAt).toLocaleDateString(), weightKg: e.weightKg }))}>
              <XAxis dataKey="date" stroke="#7c8f8c" fontSize={12} />
              <YAxis stroke="#7c8f8c" fontSize={12} domain={["auto", "auto"]} />
              <Tooltip contentStyle={{ background: "#1a2224", border: "1px solid #26302f" }} />
              <Line type="monotone" dataKey="weightKg" stroke="#22b587" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </section>
    </div>
  );
}
