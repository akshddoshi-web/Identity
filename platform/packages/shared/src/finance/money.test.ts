import { describe, expect, it } from "vitest";
import {
  addCents,
  centsToDollars,
  dollarsToCents,
  formatCents,
  percentOfCents,
  splitCentsEvenly,
  subtractCents,
} from "./money";

describe("money math (integer cents)", () => {
  it("converts dollars to cents without float drift", () => {
    expect(dollarsToCents(19.99)).toBe(1999);
    expect(dollarsToCents(0.1 + 0.2)).toBe(30);
  });

  it("converts cents back to dollars", () => {
    expect(centsToDollars(1999)).toBeCloseTo(19.99);
  });

  it("adds and subtracts cents exactly", () => {
    expect(addCents(100, 250, 33)).toBe(383);
    expect(subtractCents(500, 125)).toBe(375);
  });

  it("splits cents evenly and the parts sum back to the total", () => {
    const parts = splitCentsEvenly(1000, 3);
    expect(parts).toEqual([334, 333, 333]);
    expect(parts.reduce((a, b) => a + b, 0)).toBe(1000);
  });

  it("computes percent of cents with rounding", () => {
    expect(percentOfCents(10000, 15)).toBe(1500);
    expect(percentOfCents(333, 50)).toBe(167);
  });

  it("formats cents as currency", () => {
    expect(formatCents(1999)).toBe("$19.99");
    expect(formatCents(100000)).toBe("$1,000.00");
  });
});
