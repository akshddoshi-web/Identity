"use client";

import { formatCents } from "@identity/shared";
import { useState } from "react";
import { trpc } from "@/lib/trpc/client";

function startOfWeek() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - d.getDay());
  return d;
}
function endOfWeek() {
  const d = startOfWeek();
  d.setDate(d.getDate() + 6);
  d.setHours(23, 59, 59, 999);
  return d;
}

export default function PlannerPage() {
  const utils = trpc.useUtils();
  const from = startOfWeek();
  const to = endOfWeek();
  const week = trpc.planner.weeklyView.useQuery({ from, to });
  const templates = trpc.training.listTemplates.useQuery();
  const recipes = trpc.nutrition.listRecipes.useQuery();

  const invalidateWeek = () => utils.planner.weeklyView.invalidate({ from, to });

  const createLift = trpc.planner.createPlannedLift.useMutation({ onSuccess: invalidateWeek });
  const markSkipped = trpc.planner.markLiftSkipped.useMutation({ onSuccess: invalidateWeek });
  const createMeal = trpc.planner.createPlannedMeal.useMutation({ onSuccess: invalidateWeek });
  const logPlannedMeal = trpc.planner.logPlannedMeal.useMutation({ onSuccess: invalidateWeek });

  const [liftForm, setLiftForm] = useState({ date: "", templateId: "", label: "" });
  const [mealForm, setMealForm] = useState({ date: "", slot: "breakfast" as const, recipeId: "" });

  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(from);
    d.setDate(d.getDate() + i);
    return d;
  });

  return (
    <div className="space-y-8">
      <h1 className="text-2xl">Weekly Planner</h1>
      <p className="text-sm text-ink-400">
        Lifting, eating, and spending plans for the week — mark lifts done or skipped, one-tap log a
        planned meal as eaten, and see planned expenses due alongside them.
      </p>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-7">
        {days.map((day) => {
          const key = day.toISOString().slice(0, 10);
          const plan = week.data?.find((p) => p.date === key);
          return (
            <div key={key} className="panel min-h-[180px] p-3">
              <p className="mb-2 text-xs font-medium text-ink-400">
                {day.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
              </p>
              <div className="space-y-2 text-xs">
                {plan?.lifts.map((lift) => (
                  <div key={lift.id} className="rounded bg-ink-800 p-2">
                    <p className="text-ink-100">{lift.label}</p>
                    <p className="text-ink-500">{lift.status}</p>
                    {lift.status === "planned" && (
                      <button className="mt-1 text-ember-400 hover:underline" onClick={() => markSkipped.mutate({ plannedLiftId: lift.id })}>
                        Skip
                      </button>
                    )}
                  </div>
                ))}
                {plan?.meals.map((meal) => (
                  <div key={meal.id} className="rounded bg-ink-800 p-2">
                    <p className="capitalize text-ink-100">{meal.slot}</p>
                    {!meal.loggedEntryId && (
                      <button
                        className="text-jade-400 hover:underline"
                        onClick={() => logPlannedMeal.mutate({ plannedMealId: meal.id, loggedAt: new Date() })}
                      >
                        Log as eaten
                      </button>
                    )}
                    {meal.loggedEntryId && <p className="text-ink-500">Logged ✓</p>}
                  </div>
                ))}
                {plan?.expenses.map((expense) => (
                  <div key={expense.id} className="rounded bg-ink-800 p-2">
                    <p className="text-ink-100">{expense.description}</p>
                    <p className="text-ink-500">
                      {formatCents(expense.amountCents)} {expense.reconciledTransactionId ? "· reconciled" : ""}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <section className="panel space-y-3 p-5">
        <h2 className="text-lg">Plan a lift</h2>
        <div className="flex flex-wrap gap-2">
          <input type="date" className="input w-40" value={liftForm.date} onChange={(e) => setLiftForm((f) => ({ ...f, date: e.target.value }))} />
          <select className="input w-48" value={liftForm.templateId} onChange={(e) => setLiftForm((f) => ({ ...f, templateId: e.target.value }))}>
            <option value="">No template</option>
            {templates.data?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <input
            className="input flex-1"
            placeholder="Label (e.g. Push Day A)"
            value={liftForm.label}
            onChange={(e) => setLiftForm((f) => ({ ...f, label: e.target.value }))}
          />
          <button
            className="btn-primary"
            disabled={!liftForm.date || !liftForm.label}
            onClick={() =>
              createLift.mutate({
                scheduledDate: new Date(liftForm.date),
                templateId: liftForm.templateId || null,
                label: liftForm.label,
              })
            }
          >
            Add
          </button>
        </div>
      </section>

      <section className="panel space-y-3 p-5">
        <h2 className="text-lg">Plan a meal</h2>
        <div className="flex flex-wrap gap-2">
          <input type="date" className="input w-40" value={mealForm.date} onChange={(e) => setMealForm((f) => ({ ...f, date: e.target.value }))} />
          <select className="input w-32" value={mealForm.slot} onChange={(e) => setMealForm((f) => ({ ...f, slot: e.target.value as typeof mealForm.slot }))}>
            <option value="breakfast">Breakfast</option>
            <option value="lunch">Lunch</option>
            <option value="dinner">Dinner</option>
            <option value="snack">Snack</option>
          </select>
          <select className="input flex-1" value={mealForm.recipeId} onChange={(e) => setMealForm((f) => ({ ...f, recipeId: e.target.value }))}>
            <option value="">Select a saved recipe...</option>
            {recipes.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <button
            className="btn-primary"
            disabled={!mealForm.date || !mealForm.recipeId}
            onClick={() =>
              createMeal.mutate({
                scheduledDate: new Date(mealForm.date),
                slot: mealForm.slot,
                foodId: null,
                recipeId: mealForm.recipeId,
                quantityGrams: null,
                servings: 1,
              })
            }
          >
            Add
          </button>
        </div>
      </section>
    </div>
  );
}
