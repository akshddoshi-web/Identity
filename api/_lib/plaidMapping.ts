// Pure functions that adapt Plaid's shapes onto this app's Account/
// Transaction types. Deliberately isolated from the rest of /api and from
// src/ entirely (relative imports only, no "@/" alias — Vercel's function
// bundler doesn't read our tsconfig paths, so an alias here would work
// locally and break on deploy). Nothing here calls Plaid or touches a
// secret; it only reshapes data that's already been fetched.
import type { Account, Transaction } from "../../src/types/domain";

// The subset of Plaid's AccountBase / Transaction fields this module
// actually reads, so it doesn't need to import the full `plaid` package
// (a server-only, fairly heavy dependency) just for types.
export interface PlaidAccountLike {
  account_id: string;
  name: string;
  official_name: string | null;
  mask: string | null;
  type: string; // "depository" | "credit" | "investment" | "brokerage" | "loan" | "other"
  subtype: string | null;
  balances: { current: number | null };
}

export interface PlaidPersonalFinanceCategoryLike {
  primary?: string | null;
  detailed?: string | null;
}

export interface PlaidTransactionLike {
  transaction_id: string;
  account_id: string;
  name: string;
  merchant_name?: string | null;
  amount: number;
  date: string; // ISO yyyy-mm-dd
  personal_finance_category?: PlaidPersonalFinanceCategoryLike | null;
}

function mapAccountType(type: string, subtype: string | null): Account["type"] | null {
  if (type === "depository") {
    if (subtype === "checking") return "Checking";
    if (subtype === "savings") return "Savings";
    return null; // e.g. "cd", "money market" — no clean bucket in our closed union
  }
  if (type === "credit") return "Credit Card";
  if (type === "investment" || type === "brokerage") return "Investing";
  return null; // "loan", "other" — no bucket; caller skips these, doesn't guess
}

/**
 * Maps one Plaid account to ours, or null if it's a type our closed
 * Account["type"] union has nowhere to put (see plaidMapping's module
 * comment / the Stage 7 README notes — this is a deliberate skip, not a
 * bug). Also fixes the balance sign: Plaid reports credit balances as a
 * positive amount owed; this app has always used negative for debt (it's
 * summed straight into net worth).
 */
export function mapPlaidAccount(a: PlaidAccountLike): Account | null {
  const type = mapAccountType(a.type, a.subtype);
  if (!type) return null;

  const rawBalance = a.balances.current ?? 0;
  const balance = type === "Credit Card" ? -Math.abs(rawBalance) : rawBalance;

  return {
    id: a.account_id,
    name: a.official_name ?? a.name,
    type,
    last4: a.mask ?? "0000",
    balance,
    source: "plaid",
  };
}

export function mapPlaidAccounts(accounts: PlaidAccountLike[]): { accounts: Account[]; skipped: number } {
  const mapped = accounts.map(mapPlaidAccount);
  return {
    accounts: mapped.filter((a): a is Account => a !== null),
    skipped: mapped.filter((a) => a === null).length,
  };
}

// Plaid's personal_finance_category is a much richer taxonomy than this
// app's 6 avenue names — there's no exact, confident mapping for most of
// it. This is a best-effort heuristic, not a categorizer: high-confidence
// matches go to the closest avenue name (the same vocabulary seed
// transactions already use); everything else goes to "Other" rather than
// guessing wrong. It affects display/filtering in the Transactions list
// only — avenue.spent is not derived from this (see README).
const DETAILED_OVERRIDES: Record<string, string> = {
  GENERAL_SERVICES_SUBSCRIPTION: "Subscriptions",
  TRANSFER_OUT_SAVINGS: "Savings",
  TRANSFER_OUT_INVESTMENT_AND_RETIREMENT_FUNDS: "Investing",
  TRANSFER_IN_PAYROLL: "Income",
  TRANSFER_IN_DEPOSIT: "Income",
};

const PRIMARY_MAP: Record<string, string> = {
  INCOME: "Income",
  FOOD_AND_DRINK: "Food",
  ENTERTAINMENT: "Entertainment",
};

const FALLBACK_CATEGORY = "Other";

export function mapPlaidCategory(pfc: PlaidPersonalFinanceCategoryLike | null | undefined): string {
  if (!pfc) return FALLBACK_CATEGORY;
  if (pfc.detailed && DETAILED_OVERRIDES[pfc.detailed]) return DETAILED_OVERRIDES[pfc.detailed];
  if (pfc.primary && PRIMARY_MAP[pfc.primary]) return PRIMARY_MAP[pfc.primary];
  return FALLBACK_CATEGORY;
}

function formatPlaidDate(isoDate: string): string {
  return new Date(isoDate + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Flips Plaid's amount sign (positive = outflow) to this app's
 *  convention (negative = outflow), same reasoning as the balance flip. */
export function mapPlaidTransaction(t: PlaidTransactionLike): Transaction {
  return {
    id: t.transaction_id,
    merchant: t.merchant_name ?? t.name,
    cat: mapPlaidCategory(t.personal_finance_category),
    amt: -t.amount,
    date: formatPlaidDate(t.date),
    source: "plaid",
  };
}

export function mapPlaidTransactions(transactions: PlaidTransactionLike[]): Transaction[] {
  return transactions.map(mapPlaidTransaction);
}
