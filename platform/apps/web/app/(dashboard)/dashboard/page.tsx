"use client";

import { formatCents } from "@identity/shared";
import { StatCard } from "@/components/StatCard";
import { trpc } from "@/lib/trpc/client";

function startOfToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}
function endOfToday() {
  const d = startOfToday();
  d.setHours(23, 59, 59, 999);
  return d;
}

export default function DashboardPage() {
  const netWorth = trpc.finance.netWorth.useQuery();
  const dailySummary = trpc.nutrition.dailySummary.useQuery({ date: startOfToday() });
  const today = trpc.planner.weeklyView.useQuery({ from: startOfToday(), to: endOfToday() });

  const todayPlan = today.data?.[0];
  const macroTotals = dailySummary.data?.totals;
  const macroTargets = dailySummary.data?.targets;

  return (
    <div className="space-y-8">
      <h1 className="text-2xl">Overview</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Net worth"
          value={netWorth.data ? formatCents(netWorth.data.netWorthCents) : "—"}
          accent="jade"
        />
        <StatCard
          label="Calories today"
          value={macroTotals ? `${Math.round(macroTotals.calories)} kcal` : "—"}
          sublabel={macroTargets ? `target ${macroTargets.calories} kcal` : undefined}
          accent="ember"
        />
        <StatCard
          label="Protein today"
          value={macroTotals ? `${Math.round(macroTotals.proteinG)} g` : "—"}
          sublabel={macroTargets ? `target ${macroTargets.proteinG} g` : undefined}
          accent="gold"
        />
      </div>

      <div className="panel p-5">
        <h2 className="mb-3 text-lg">Today's plan</h2>
        {!todayPlan && <p className="text-sm text-ink-400">Nothing scheduled today. Head to Planner to add lifts, meals, or expenses.</p>}
        {todayPlan && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <p className="label">Lifts</p>
              {todayPlan.lifts.length === 0 && <p className="text-sm text-ink-500">None planned</p>}
              {todayPlan.lifts.map((lift) => (
                <p key={lift.id} className="text-sm text-ink-200">
                  {lift.label} — <span className="text-ink-400">{lift.status}</span>
                </p>
              ))}
            </div>
            <div>
              <p className="label">Meals</p>
              {todayPlan.meals.length === 0 && <p className="text-sm text-ink-500">None planned</p>}
              {todayPlan.meals.map((meal) => (
                <p key={meal.id} className="text-sm text-ink-200 capitalize">
                  {meal.slot}
                </p>
              ))}
            </div>
            <div>
              <p className="label">Expenses due</p>
              {todayPlan.expenses.length === 0 && <p className="text-sm text-ink-500">None due</p>}
              {todayPlan.expenses.map((expense) => (
                <p key={expense.id} className="text-sm text-ink-200">
                  {expense.description} — {formatCents(expense.amountCents)}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
