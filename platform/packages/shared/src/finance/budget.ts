import { type Cents, addCents } from "./money";

export interface BudgetPeriodInput {
  limitCents: Cents;
  spentCents: Cents;
}

export type BudgetStatus = "under" | "approaching" | "at_limit" | "over";

export interface BudgetProgress {
  limitCents: Cents;
  spentCents: Cents;
  remainingCents: Cents;
  percentUsed: number;
  status: BudgetStatus;
}

/** Percent of a budget's limit at which we start warning the user. */
export const APPROACHING_THRESHOLD_PERCENT = 80;

export function evaluateBudget({ limitCents, spentCents }: BudgetPeriodInput): BudgetProgress {
  if (limitCents <= 0) throw new Error("limitCents must be > 0");
  const percentUsed = Math.round((spentCents / limitCents) * 100);
  const remainingCents = limitCents - spentCents;

  let status: BudgetStatus = "under";
  if (spentCents > limitCents) status = "over";
  else if (spentCents === limitCents) status = "at_limit";
  else if (percentUsed >= APPROACHING_THRESHOLD_PERCENT) status = "approaching";

  return { limitCents, spentCents, remainingCents, percentUsed, status };
}

export interface NetWorthSnapshotInput {
  assetAccountsCents: Cents[];
  liabilityAccountsCents: Cents[];
}

/** Liability account balances are stored as positive cents owed. */
export function computeNetWorthCents({
  assetAccountsCents,
  liabilityAccountsCents,
}: NetWorthSnapshotInput): Cents {
  const assets = addCents(...assetAccountsCents);
  const liabilities = addCents(...liabilityAccountsCents);
  return assets - liabilities;
}

export interface TransactionLike {
  id: string;
  merchantName: string;
  amountCents: Cents;
  postedAt: Date;
}

export interface RecurringGroup {
  merchantName: string;
  approxAmountCents: Cents;
  cadence: "monthly" | "annual";
  transactionIds: string[];
}

const MS_PER_DAY = 1000 * 60 * 60 * 24;

/**
 * Flags merchants that charge a similar amount at roughly monthly or annual
 * intervals as likely recurring subscriptions/bills. Intentionally simple
 * (tolerance-based clustering) rather than a trained model, per spec: layer
 * more sophisticated detection on top later if false positive rate is high.
 */
export function detectRecurringTransactions(
  transactions: TransactionLike[],
  options: { amountTolerancePercent?: number; minOccurrences?: number } = {},
): RecurringGroup[] {
  const amountTolerancePercent = options.amountTolerancePercent ?? 10;
  const minOccurrences = options.minOccurrences ?? 2;

  const byMerchant = new Map<string, TransactionLike[]>();
  for (const tx of transactions) {
    const key = tx.merchantName.trim().toLowerCase();
    if (!byMerchant.has(key)) byMerchant.set(key, []);
    byMerchant.get(key)!.push(tx);
  }

  const groups: RecurringGroup[] = [];

  for (const [merchantName, txs] of byMerchant) {
    if (txs.length < minOccurrences) continue;
    const sorted = [...txs].sort((a, b) => a.postedAt.getTime() - b.postedAt.getTime());

    for (const cadence of ["monthly", "annual"] as const) {
      const expectedDays = cadence === "monthly" ? 30 : 365;
      const dayTolerance = cadence === "monthly" ? 6 : 20;

      const cluster: TransactionLike[] = [sorted[0]];
      for (let i = 1; i < sorted.length; i++) {
        const prev = cluster[cluster.length - 1];
        const gapDays = (sorted[i].postedAt.getTime() - prev.postedAt.getTime()) / MS_PER_DAY;
        const amountDiffPercent =
          (Math.abs(sorted[i].amountCents - prev.amountCents) / Math.abs(prev.amountCents || 1)) *
          100;

        if (
          Math.abs(gapDays - expectedDays) <= dayTolerance &&
          amountDiffPercent <= amountTolerancePercent
        ) {
          cluster.push(sorted[i]);
        }
      }

      if (cluster.length >= minOccurrences) {
        const avgAmount = Math.round(
          cluster.reduce((sum, t) => sum + t.amountCents, 0) / cluster.length,
        );
        groups.push({
          merchantName,
          approxAmountCents: avgAmount,
          cadence,
          transactionIds: cluster.map((t) => t.id),
        });
        break;
      }
    }
  }

  return groups;
}

export interface CategorizationRule {
  /** Matched case-insensitively against merchant name or Plaid category. */
  pattern: string;
  category: string;
}

/**
 * Layer of user-defined overrides on top of the provider's category data.
 * `plaidCategory` is used as the default; a matching user rule (by merchant
 * substring) wins, mirroring "system learns from user overrides".
 */
export function categorizeTransaction(
  input: { merchantName: string; plaidCategory: string | null },
  userRules: CategorizationRule[],
): string {
  const merchant = input.merchantName.toLowerCase();
  const matchingRule = userRules.find((rule) => merchant.includes(rule.pattern.toLowerCase()));
  if (matchingRule) return matchingRule.category;
  return input.plaidCategory ?? "Uncategorized";
}
