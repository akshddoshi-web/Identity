import { describe, expect, it } from "vitest";
import { buildStatusItems } from "./statusOverview";
import { homeSeed } from "@/data/homeSeed";
import { stocksSeed } from "@/data/stocksSeed";
import { fitnessSeed } from "@/data/fitnessSeed";
import { plannerSeed } from "@/data/plannerSeed";

const REAL_INPUTS = {
  avenues: homeSeed.avenues,
  stocks: stocksSeed.stocks,
  fitness: fitnessSeed,
  week: plannerSeed.week,
};

describe("buildStatusItems", () => {
  it("puts every crit-tone item before every warn-tone item, regardless of severity", () => {
    const items = buildStatusItems(REAL_INPUTS);
    const firstWarnIndex = items.findIndex((i) => i.tone === "warn");
    const lastCritIndex = items.map((i) => i.tone).lastIndexOf("crit");
    expect(firstWarnIndex).toBeGreaterThan(-1);
    expect(lastCritIndex).toBeGreaterThan(-1);
    expect(lastCritIndex).toBeLessThan(firstWarnIndex);
  });

  it("orders items within a tone by severity, descending", () => {
    const items = buildStatusItems(REAL_INPUTS);
    for (let i = 1; i < items.length; i++) {
      if (items[i].tone === items[i - 1].tone) {
        expect(items[i].severity).toBeLessThanOrEqual(items[i - 1].severity);
      }
    }
  });

  it("ranks the real seed data's schedule alert above the entertainment budget alert", () => {
    // Planner's schedule is at 25% completion (severity 0.75, crit); Home's
    // Entertainment avenue is 18% over budget (severity 0.18, crit). Both
    // crit, so severity should decide it, and it's not close.
    const items = buildStatusItems(REAL_INPUTS);
    const schedule = items.find((i) => i.id === "planner-schedule")!;
    const entertainment = items.find((i) => i.id === "home-ave-entertainment-crit")!;
    expect(schedule).toBeDefined();
    expect(entertainment).toBeDefined();
    expect(items.indexOf(schedule)).toBeLessThan(items.indexOf(entertainment));
  });

  it("ranks a mild ceiling warn (Food, just under budget) below the other real warn alerts", () => {
    // Food is 94.5% of budget — inside the warn band but technically under
    // target, so its severity (ratio - 1) comes out slightly negative. That's
    // not a bug: it should still sort last among warn-tier items, since it's
    // the least severe of them, not first.
    const items = buildStatusItems(REAL_INPUTS);
    const warnItems = items.filter((i) => i.tone === "warn");
    const food = warnItems.find((i) => i.id === "home-ave-food-warn");
    expect(food).toBeDefined();
    expect(food!.severity).toBeLessThan(0);
    expect(warnItems[warnItems.length - 1].id).toBe(food!.id);
  });

  it("excludes stocks with no rule-based flag (tone 'ok') from the list entirely", () => {
    const items = buildStatusItems(REAL_INPUTS);
    // AAPL and VTI have no flags in the seed data — they must not appear.
    expect(items.some((i) => i.id === "stocks-AAPL")).toBe(false);
    expect(items.some((i) => i.id === "stocks-VTI")).toBe(false);
  });

  it("links a held stock's alert to its portfolio detail page, and a watchlist stock's alert to its watchlist detail page", () => {
    const items = buildStatusItems(REAL_INPUTS);
    const nvda = items.find((i) => i.id === "stocks-NVDA")!;
    const coin = items.find((i) => i.id === "stocks-COIN")!;
    expect(nvda.href).toBe("/stocks/portfolio/nvda");
    expect(coin.href).toBe("/stocks/watchlist/coin");
  });

  it("has no Fantasy items — points-based competition has no target/goal shape for the engine", () => {
    const items = buildStatusItems(REAL_INPUTS);
    expect(items.some((i) => i.domain === ("Fantasy" as never))).toBe(false);
  });

  it("returns an empty list when nothing is out of range in any domain", () => {
    const onTrack = {
      avenues: REAL_INPUTS.avenues.map((a) => ({ ...a, spent: 0 })),
      // held:false neutralizes the concentration check; a zero-width day
      // range (equal to the stock's own price) neutralizes the volatility
      // check, which — unlike concentration — applies to every stock
      // regardless of held status.
      stocks: REAL_INPUTS.stocks.map((s) => ({
        ...s,
        held: false,
        dayRange: `${s.price.toFixed(2)} – ${s.price.toFixed(2)}`,
      })),
      fitness: {
        ...REAL_INPUTS.fitness,
        macros: {
          cal: { cur: 0, goal: 2200 },
          protein: { cur: 170, goal: 170 },
          carbs: { cur: 0, goal: 220 },
          fat: { cur: 0, goal: 70 },
        },
        // Give every lift a full (3-set) most-recent session, so this
        // week's Push/Legs/Pull all read as complete — the seed data
        // deliberately leaves Deadlift's most recent session short (see
        // fitnessSeed.ts) to demo the workout-completion alert elsewhere.
        lifts: REAL_INPUTS.fitness.lifts.map((l) => ({
          ...l,
          sessions: l.sessions.map((session, i, arr) =>
            i === arr.length - 1
              ? {
                  ...session,
                  sets: [
                    { weight: 100, reps: 5, rpe: 6 },
                    { weight: 105, reps: 5, rpe: 7 },
                    { weight: 110, reps: 5, rpe: 8 },
                  ],
                }
              : session,
          ),
        })),
      },
      week: Object.fromEntries(
        Object.entries(REAL_INPUTS.week).map(([day, blocks]) => [day, blocks.map((b) => ({ ...b, done: true }))]),
      ) as typeof REAL_INPUTS.week,
    };
    expect(buildStatusItems(onTrack)).toEqual([]);
  });
});
