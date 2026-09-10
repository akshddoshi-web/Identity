import { describe, expect, it } from "vitest";
import { runSimplifiedBacktest, scoreRiskTolerance, suggestAllocation } from "./allocation";
import type { ScoredStock } from "./scoring";

function scored(symbol: string, compositeScore: number): ScoredStock {
  return {
    symbol,
    sector: "Technology",
    compositeScore,
    subScores: { valuation: null, momentum: null, volatility: null, volumeTrend: null, fundamentals: null },
  };
}

describe("scoreRiskTolerance", () => {
  it("scores a long horizon, high comfort, funded user as aggressive", () => {
    expect(
      scoreRiskTolerance({ timeHorizonYears: 20, drawdownComfort: 4, hasEmergencyFund: true }),
    ).toBe(5);
  });

  it("scores a short horizon, low comfort, unfunded user as conservative", () => {
    expect(
      scoreRiskTolerance({ timeHorizonYears: 1, drawdownComfort: 2, hasEmergencyFund: false }),
    ).toBe(1);
  });

  it("clamps to the 1-5 range", () => {
    expect(
      scoreRiskTolerance({ timeHorizonYears: 30, drawdownComfort: 5, hasEmergencyFund: true }),
    ).toBeLessThanOrEqual(5);
  });
});

describe("suggestAllocation", () => {
  it("returns empty for an empty universe", () => {
    expect(suggestAllocation([], 3)).toEqual([]);
  });

  it("weights sum to ~100%", () => {
    const universe = [scored("A", 2), scored("B", 1), scored("C", 0.5)];
    const allocation = suggestAllocation(universe, 3);
    const total = allocation.reduce((sum, a) => sum + a.weightPercent, 0);
    expect(total).toBeCloseTo(100, 1);
  });

  it("gives the top-scored stock more weight than lower-scored ones", () => {
    const universe = [scored("BEST", 3), scored("MID", 1), scored("WORST", -1)];
    const allocation = suggestAllocation(universe, 3);
    const byWeight = Object.fromEntries(allocation.map((a) => [a.symbol, a.weightPercent]));
    expect(byWeight.BEST).toBeGreaterThan(byWeight.MID);
    expect(byWeight.MID).toBeGreaterThan(byWeight.WORST);
  });

  it("concentrates more into top picks at higher risk tolerance", () => {
    const universe = [scored("BEST", 3), scored("MID", 1), scored("WORST", -1)];
    const conservative = suggestAllocation(universe, 1);
    const aggressive = suggestAllocation(universe, 5);
    const bestWeight = (allocation: typeof conservative) =>
      allocation.find((a) => a.symbol === "BEST")!.weightPercent;
    expect(bestWeight(aggressive)).toBeGreaterThan(bestWeight(conservative));
  });

  it("caps positions based on risk tolerance", () => {
    const universe = Array.from({ length: 20 }, (_, i) => scored(`S${i}`, 20 - i));
    expect(suggestAllocation(universe, 5).length).toBeLessThanOrEqual(6);
    expect(suggestAllocation(universe, 1).length).toBeLessThanOrEqual(15);
  });
});

describe("runSimplifiedBacktest", () => {
  it("blends trailing returns by allocation weight and always includes a disclaimer", () => {
    const result = runSimplifiedBacktest({
      allocation: [
        { symbol: "A", weightPercent: 50 },
        { symbol: "B", weightPercent: 50 },
      ],
      trailingReturnBySymbol: { A: 0.2, B: -0.1 },
    });
    expect(result.weightedReturnPercent).toBeCloseTo(5, 1); // 0.5*20 + 0.5*-10
    expect(result.disclaimer.length).toBeGreaterThan(0);
  });

  it("treats a missing return as 0 rather than throwing", () => {
    const result = runSimplifiedBacktest({
      allocation: [{ symbol: "UNKNOWN", weightPercent: 100 }],
      trailingReturnBySymbol: {},
    });
    expect(result.weightedReturnPercent).toBe(0);
  });
});
