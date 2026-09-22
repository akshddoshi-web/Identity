// A consumer of consumers: pulls the already-computed alerts from every
// domain's own insight function (buildAvenueAlerts, buildStockInsights,
// buildFitnessAlerts, buildScheduleAlert) and ranks them together. Nothing
// here re-derives a tone or a threshold — that logic lives exactly once,
// in evaluateTarget(). This module only normalizes shape and orders the
// result. Fantasy has no consumer here, by design (see accountability.ts
// and the Stage 5 README notes) — points-based competition has no
// actual-vs-target-with-a-goal shape for the engine to evaluate.
import { buildAvenueAlerts, type AlertTone } from "./accountability";
import { buildStockInsights } from "./stockInsights";
import { buildFitnessAlerts } from "./fitnessInsights";
import { buildScheduleAlert } from "./plannerInsights";
import type { Avenue } from "@/types/domain";
import type { Stock } from "@/types/stocks";
import type { FitnessData } from "@/types/fitness";
import type { WeekPlan } from "@/types/planner";

export type StatusDomain = "Home" | "Stocks" | "Fitness" | "Planner";

export interface StatusItem {
  id: string;
  domain: StatusDomain;
  tone: AlertTone;
  title: string;
  body: string;
  severity: number;
  /** Where clicking this item takes you — the most specific/actionable
   *  page for it, same principle as "a stock alert opens that stock's
   *  detail page," not necessarily the literal card it also renders on. */
  href: string;
}

export interface StatusInputs {
  avenues: Avenue[];
  stocks: Stock[];
  fitness: FitnessData;
  week: WeekPlan;
}

/**
 * Every currently-firing alert across Home, Stocks, Fitness, and Planner,
 * sorted worst-first: tone (crit before warn) is the primary key, since
 * that ordering is each domain's own deliberate judgment call (crit
 * thresholds are always the more extreme line); `severity` — how far past
 * target, as a fraction of target, direction-normalized — breaks ties
 * within a tone so a domain with a wider miss still sorts above a domain
 * with a narrower one, without needing to know either domain's units.
 */
export function buildStatusItems(inputs: StatusInputs): StatusItem[] {
  const items: StatusItem[] = [];

  for (const a of buildAvenueAlerts(inputs.avenues)) {
    items.push({
      id: `home-${a.id}`,
      domain: "Home",
      tone: a.tone,
      title: a.title,
      body: a.body,
      severity: a.severity,
      href: "/home/budgets",
    });
  }

  for (const s of buildStockInsights(inputs.stocks)) {
    if (s.tone === "ok") continue;
    const stock = inputs.stocks.find((x) => x.ticker === s.ticker);
    const sub = stock?.held ? "portfolio" : "watchlist";
    items.push({
      id: `stocks-${s.ticker}`,
      domain: "Stocks",
      tone: s.tone,
      title: s.title,
      body: s.note,
      severity: s.severity ?? 0,
      href: `/stocks/${sub}/${s.ticker.toLowerCase()}`,
    });
  }

  const FITNESS_HREF: Record<string, string> = {
    calories: "/fitness/today",
    protein: "/fitness/today",
    "workout-completion": "/fitness/lifts",
  };
  for (const f of buildFitnessAlerts(inputs.fitness)) {
    items.push({
      id: `fitness-${f.id}`,
      domain: "Fitness",
      tone: f.tone,
      title: f.title,
      body: f.body,
      severity: f.severity,
      href: FITNESS_HREF[f.id] ?? "/fitness/today",
    });
  }

  const schedule = buildScheduleAlert(inputs.week);
  if (schedule) {
    items.push({
      id: `planner-${schedule.id}`,
      domain: "Planner",
      tone: schedule.tone,
      title: schedule.title,
      body: schedule.body,
      severity: schedule.severity,
      href: "/planner/week",
    });
  }

  return items.sort((a, b) => {
    if (a.tone !== b.tone) return a.tone === "crit" ? -1 : 1;
    return b.severity - a.severity;
  });
}
