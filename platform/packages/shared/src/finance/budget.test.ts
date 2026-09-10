import { describe, expect, it } from "vitest";
import {
  categorizeTransaction,
  computeNetWorthCents,
  detectRecurringTransactions,
  evaluateBudget,
} from "./budget";

describe("evaluateBudget", () => {
  it("is under when spend is low", () => {
    const result = evaluateBudget({ limitCents: 10000, spentCents: 2000 });
    expect(result.status).toBe("under");
    expect(result.remainingCents).toBe(8000);
  });

  it("is approaching at the 80% threshold", () => {
    const result = evaluateBudget({ limitCents: 10000, spentCents: 8000 });
    expect(result.status).toBe("approaching");
  });

  it("is at_limit when spend equals the limit exactly", () => {
    const result = evaluateBudget({ limitCents: 10000, spentCents: 10000 });
    expect(result.status).toBe("at_limit");
  });

  it("is over when spend exceeds the limit", () => {
    const result = evaluateBudget({ limitCents: 10000, spentCents: 12000 });
    expect(result.status).toBe("over");
    expect(result.remainingCents).toBe(-2000);
  });

  it("rejects a non-positive limit", () => {
    expect(() => evaluateBudget({ limitCents: 0, spentCents: 100 })).toThrow();
  });
});

describe("computeNetWorthCents", () => {
  it("subtracts liabilities from assets", () => {
    expect(
      computeNetWorthCents({
        assetAccountsCents: [500000, 250000],
        liabilityAccountsCents: [150000],
      }),
    ).toBe(600000);
  });

  it("can be negative when liabilities exceed assets", () => {
    expect(
      computeNetWorthCents({ assetAccountsCents: [1000], liabilityAccountsCents: [5000] }),
    ).toBe(-4000);
  });
});

describe("categorizeTransaction", () => {
  it("falls back to the provider category with no matching rule", () => {
    expect(
      categorizeTransaction({ merchantName: "Trader Joe's", plaidCategory: "Groceries" }, []),
    ).toBe("Groceries");
  });

  it("prefers a matching user override rule", () => {
    expect(
      categorizeTransaction(
        { merchantName: "Trader Joe's #123", plaidCategory: "Groceries" },
        [{ pattern: "trader joe", category: "Food & Dining" }],
      ),
    ).toBe("Food & Dining");
  });

  it("defaults to Uncategorized with no provider category or rule", () => {
    expect(categorizeTransaction({ merchantName: "Unknown Corp", plaidCategory: null }, [])).toBe(
      "Uncategorized",
    );
  });
});

describe("detectRecurringTransactions", () => {
  function tx(id: string, merchantName: string, amountCents: number, postedAt: string) {
    return { id, merchantName, amountCents, postedAt: new Date(postedAt) };
  }

  it("flags a monthly subscription charged at a consistent amount", () => {
    const groups = detectRecurringTransactions([
      tx("1", "Netflix", 1599, "2024-01-05"),
      tx("2", "Netflix", 1599, "2024-02-05"),
      tx("3", "Netflix", 1599, "2024-03-06"),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0]).toMatchObject({ merchantName: "netflix", cadence: "monthly" });
  });

  it("does not flag a one-off purchase", () => {
    const groups = detectRecurringTransactions([tx("1", "Best Buy", 45000, "2024-01-05")]);
    expect(groups).toHaveLength(0);
  });

  it("does not flag irregular, differently-priced charges", () => {
    const groups = detectRecurringTransactions([
      tx("1", "Amazon", 2399, "2024-01-05"),
      tx("2", "Amazon", 9999, "2024-01-20"),
      tx("3", "Amazon", 500, "2024-03-11"),
    ]);
    expect(groups).toHaveLength(0);
  });

  it("flags an annual charge", () => {
    const groups = detectRecurringTransactions([
      tx("1", "Amazon Prime", 13900, "2023-06-01"),
      tx("2", "Amazon Prime", 13900, "2024-06-03"),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].cadence).toBe("annual");
  });
});
