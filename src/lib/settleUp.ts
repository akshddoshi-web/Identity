// Generic multi-party debt simplification — the "Splitwise" algorithm.
// Deliberately knows nothing about leagues, points, or money sources: it
// takes a flat list of net balances (positive = owed to them, negative =
// they owe) and returns the minimal set of payments that zeroes everyone
// out. Domain-specific callers (fantasy leagues today) build the balance
// list and hand it here, the same way stockInsights.ts feeds
// accountability.ts's evaluateTarget() rather than reimplementing it.
export interface Balance {
  who: string;
  amount: number;
}

export interface Payment {
  from: string;
  to: string;
  amount: number;
}

const EPSILON = 0.005; // half a cent — absorbs floating point noise, not real debt

/**
 * Collapses a list of balances (possibly with repeated names, e.g. the same
 * person appearing in several leagues) into the minimal set of payments
 * that settles every net creditor and debtor to zero. Greedy largest
 * creditor vs. largest debtor at each step — the standard practical
 * "min cash flow" approach, not a global minimum-transaction-count solver
 * (that's NP-hard in general), but it's what Splitwise itself does.
 */
export function settleUp(balances: Balance[]): Payment[] {
  const net = new Map<string, number>();
  for (const b of balances) {
    net.set(b.who, (net.get(b.who) ?? 0) + b.amount);
  }

  const creditors: { who: string; amount: number }[] = [];
  const debtors: { who: string; amount: number }[] = [];
  for (const [who, amount] of net) {
    if (amount > EPSILON) creditors.push({ who, amount });
    else if (amount < -EPSILON) debtors.push({ who, amount: -amount });
  }
  creditors.sort((a, b) => b.amount - a.amount);
  debtors.sort((a, b) => b.amount - a.amount);

  const payments: Payment[] = [];
  let ci = 0;
  let di = 0;
  while (ci < creditors.length && di < debtors.length) {
    const c = creditors[ci];
    const d = debtors[di];
    const amount = Math.min(c.amount, d.amount);

    if (amount > EPSILON) {
      payments.push({ from: d.who, to: c.who, amount: Math.round(amount * 100) / 100 });
    }

    c.amount -= amount;
    d.amount -= amount;
    if (c.amount <= EPSILON) ci++;
    if (d.amount <= EPSILON) di++;
  }

  return payments;
}
