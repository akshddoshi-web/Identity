import { describe, expect, it } from "vitest";
import {
  DEFAULT_FACTOR_WEIGHTS,
  rankStocks,
  rankStocksBySector,
  scoreStockUniverse,
  type StockFactors,
} from "./scoring";

function stock(overrides: Partial<StockFactors> & { symbol: string }): StockFactors {
  return {
    sector: "Technology",
    peRatio: 20,
    pbRatio: 4,
    momentum3m: 0.05,
    momentum6m: 0.1,
    momentum12m: 0.15,
    volatility: 0.2,
    volumeTrend: 1.0,
    revenueGrowth: 0.1,
    netMargin: 0.15,
    debtToEquity: 0.5,
    ...overrides,
  };
}

describe("scoreStockUniverse", () => {
  it("returns empty for an empty universe", () => {
    expect(scoreStockUniverse([])).toEqual([]);
  });

  it("scores a cheaper, higher-momentum stock above an expensive, weak one", () => {
    const cheapMomentum = stock({ symbol: "GOOD", peRatio: 10, pbRatio: 2, momentum12m: 0.4 });
    const expensiveWeak = stock({ symbol: "BAD", peRatio: 60, pbRatio: 15, momentum12m: -0.2 });
    const neutral = stock({ symbol: "MID" });

    const scored = scoreStockUniverse([cheapMomentum, expensiveWeak, neutral]);
    const ranked = rankStocks(scored);

    expect(ranked[0].symbol).toBe("GOOD");
    expect(ranked[ranked.length - 1].symbol).toBe("BAD");
  });

  it("does not penalize a stock for a missing data field", () => {
    const missingPe = stock({ symbol: "NOPE", peRatio: null });
    const scored = scoreStockUniverse([missingPe, stock({ symbol: "OTHER" })]);
    const nope = scored.find((s) => s.symbol === "NOPE")!;
    expect(nope.subScores.valuation).not.toBeNull();
    expect(Number.isFinite(nope.compositeScore)).toBe(true);
  });

  it("returns null sub-scores when a factor has no variance across the universe", () => {
    const scored = scoreStockUniverse([
      stock({ symbol: "A", volatility: 0.2 }),
      stock({ symbol: "B", volatility: 0.2 }),
    ]);
    expect(scored[0].subScores.volatility).toBe(0);
  });

  it("respects custom factor weights (pure momentum tilt)", () => {
    const momentumOnly = {
      ...DEFAULT_FACTOR_WEIGHTS,
      valuation: 0,
      volatility: 0,
      volumeTrend: 0,
      fundamentals: 0,
      momentum: 1,
    };
    const highMomentumBadValue = stock({
      symbol: "HIGHMOM",
      momentum12m: 0.5,
      peRatio: 200,
    });
    const lowMomentumGoodValue = stock({
      symbol: "LOWMOM",
      momentum12m: -0.3,
      peRatio: 5,
    });
    const scored = scoreStockUniverse([highMomentumBadValue, lowMomentumGoodValue], momentumOnly);
    const ranked = rankStocks(scored);
    expect(ranked[0].symbol).toBe("HIGHMOM");
  });
});

describe("rankStocksBySector", () => {
  it("groups and ranks within each sector independently", () => {
    const scored = scoreStockUniverse([
      stock({ symbol: "TECH_GOOD", sector: "Technology", momentum12m: 0.5 }),
      stock({ symbol: "TECH_BAD", sector: "Technology", momentum12m: -0.5 }),
      stock({ symbol: "HEALTH_GOOD", sector: "Healthcare", momentum12m: 0.5 }),
      stock({ symbol: "HEALTH_BAD", sector: "Healthcare", momentum12m: -0.5 }),
    ]);
    const bySector = rankStocksBySector(scored);
    expect(bySector.get("Technology")!.map((s) => s.symbol)).toEqual(["TECH_GOOD", "TECH_BAD"]);
    expect(bySector.get("Healthcare")!.map((s) => s.symbol)).toEqual([
      "HEALTH_GOOD",
      "HEALTH_BAD",
    ]);
  });
});
