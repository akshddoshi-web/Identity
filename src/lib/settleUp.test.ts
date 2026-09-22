import { describe, expect, it } from "vitest";
import { settleUp } from "./settleUp";

function totalsByPerson(payments: { from: string; to: string; amount: number }[]) {
  const net = new Map<string, number>();
  for (const p of payments) {
    net.set(p.from, (net.get(p.from) ?? 0) - p.amount);
    net.set(p.to, (net.get(p.to) ?? 0) + p.amount);
  }
  return net;
}

describe("settleUp", () => {
  it("returns nothing for an already-settled set of balances", () => {
    expect(settleUp([{ who: "A", amount: 0 }, { who: "B", amount: 0 }])).toEqual([]);
  });

  it("settles a simple two-person debt in one payment", () => {
    const payments = settleUp([
      { who: "A", amount: 10 },
      { who: "B", amount: -10 },
    ]);
    expect(payments).toEqual([{ from: "B", to: "A", amount: 10 }]);
  });

  it("never produces more payments than there are non-zero balances", () => {
    const balances = [
      { who: "A", amount: 30 },
      { who: "B", amount: -10 },
      { who: "C", amount: -10 },
      { who: "D", amount: -10 },
    ];
    const payments = settleUp(balances);
    expect(payments.length).toBeLessThanOrEqual(balances.length);
    // every debtor pays A directly — no unnecessary intermediate hops
    expect(payments.every((p) => p.to === "A")).toBe(true);
  });

  it("merges repeated names (the same person across multiple leagues) before settling", () => {
    // "You" is +14 in one league and -18 in another — net -4, a debtor,
    // not two separate obligations.
    const balances = [
      { who: "You", amount: 14 },
      { who: "Mike", amount: -14 },
      { who: "You", amount: -18 },
      { who: "Chris", amount: 18 },
    ];
    const payments = settleUp(balances);
    const net = totalsByPerson(payments);
    expect(net.get("You")).toBeCloseTo(-4, 5);
    expect(net.get("Mike")).toBeCloseTo(-14, 5);
    expect(net.get("Chris")).toBeCloseTo(18, 5);
  });

  it("zeroes out every participant for an arbitrary multi-party set", () => {
    const balances = [
      { who: "You", amount: -4 },
      { who: "Mike", amount: 2 },
      { who: "Sarah", amount: -6 },
      { who: "Priya", amount: -10 },
      { who: "Chris", amount: 72 },
      { who: "Ana", amount: 18 },
      { who: "Deion", amount: -36 },
      { who: "Wes", amount: -36 },
    ];
    const payments = settleUp(balances);
    const net = totalsByPerson(payments);

    for (const b of balances) {
      expect(net.get(b.who) ?? 0).toBeCloseTo(b.amount, 5);
    }
  });

  it("ignores balances that are already zero within floating-point noise", () => {
    const payments = settleUp([
      { who: "A", amount: 0.001 },
      { who: "B", amount: -0.001 },
      { who: "C", amount: 5 },
      { who: "D", amount: -5 },
    ]);
    expect(payments).toEqual([{ from: "D", to: "C", amount: 5 }]);
  });

  it("returns an empty list for no balances", () => {
    expect(settleUp([])).toEqual([]);
  });
});
