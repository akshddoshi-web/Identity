import { describe, expect, it } from "vitest";
import { annualizedVolatility, tradingDaysAgoReturn, volumeTrend } from "./marketData";

describe("tradingDaysAgoReturn", () => {
  it("computes return over N trading days (newest-first array)", () => {
    const closes = [110, 108, 105, 100]; // index 0 = today, index 3 = 3 trading days ago
    expect(tradingDaysAgoReturn(closes, 3)).toBeCloseTo(110 / 100 - 1);
  });

  it("returns null when there isn't enough history", () => {
    expect(tradingDaysAgoReturn([100, 99], 5)).toBeNull();
  });
});

describe("annualizedVolatility", () => {
  it("returns null with insufficient history", () => {
    expect(annualizedVolatility([100, 101, 99])).toBeNull();
  });

  it("returns 0 for a perfectly flat price series", () => {
    const flat = Array(40).fill(100);
    expect(annualizedVolatility(flat)).toBe(0);
  });

  it("is higher for a more volatile series", () => {
    const calm = Array.from({ length: 40 }, (_, i) => 100 + (i % 2 === 0 ? 0.1 : -0.1));
    const wild = Array.from({ length: 40 }, (_, i) => 100 + (i % 2 === 0 ? 10 : -10));
    expect(annualizedVolatility(wild)!).toBeGreaterThan(annualizedVolatility(calm)!);
  });
});

describe("volumeTrend", () => {
  it("returns null with insufficient history", () => {
    expect(volumeTrend([1000, 2000])).toBeNull();
  });

  it("is > 1 when recent volume is elevated vs. the trailing average", () => {
    const recentHigh = [...Array(20).fill(2000), ...Array(40).fill(1000)];
    expect(volumeTrend(recentHigh)!).toBeGreaterThan(1);
  });

  it("is 1 for flat volume", () => {
    expect(volumeTrend(Array(60).fill(1000))).toBe(1);
  });
});
