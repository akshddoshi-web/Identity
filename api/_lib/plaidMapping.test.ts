import { describe, expect, it } from "vitest";
import {
  mapPlaidAccount,
  mapPlaidAccounts,
  mapPlaidCategory,
  mapPlaidTransaction,
  type PlaidAccountLike,
  type PlaidTransactionLike,
} from "./plaidMapping";

function account(overrides: Partial<PlaidAccountLike>): PlaidAccountLike {
  return {
    account_id: "acc-1",
    name: "Plaid Checking",
    official_name: null,
    mask: "1234",
    type: "depository",
    subtype: "checking",
    balances: { current: 100 },
    ...overrides,
  };
}

function transaction(overrides: Partial<PlaidTransactionLike>): PlaidTransactionLike {
  return {
    transaction_id: "tx-1",
    account_id: "acc-1",
    name: "SPARKFUN",
    merchant_name: null,
    amount: 10,
    date: "2026-09-18",
    personal_finance_category: null,
    ...overrides,
  };
}

describe("mapPlaidAccount", () => {
  it("maps checking/savings/credit/investment types onto our union", () => {
    expect(mapPlaidAccount(account({ type: "depository", subtype: "checking" }))?.type).toBe("Checking");
    expect(mapPlaidAccount(account({ type: "depository", subtype: "savings" }))?.type).toBe("Savings");
    expect(mapPlaidAccount(account({ type: "credit", subtype: "credit card" }))?.type).toBe("Credit Card");
    expect(mapPlaidAccount(account({ type: "investment", subtype: "401k" }))?.type).toBe("Investing");
    expect(mapPlaidAccount(account({ type: "brokerage", subtype: "brokerage" }))?.type).toBe("Investing");
  });

  it("returns null (skips) for account types with no home in our closed union", () => {
    expect(mapPlaidAccount(account({ type: "loan", subtype: "mortgage" }))).toBeNull();
    expect(mapPlaidAccount(account({ type: "depository", subtype: "cd" }))).toBeNull();
    expect(mapPlaidAccount(account({ type: "other", subtype: null }))).toBeNull();
  });

  it("flips a credit account's balance to negative (debt), regardless of Plaid's sign", () => {
    const mapped = mapPlaidAccount(account({ type: "credit", subtype: "credit card", balances: { current: 450.25 } }));
    expect(mapped?.balance).toBe(-450.25);
  });

  it("leaves a non-credit account's balance sign untouched", () => {
    const mapped = mapPlaidAccount(account({ type: "depository", subtype: "checking", balances: { current: 1840.22 } }));
    expect(mapped?.balance).toBe(1840.22);
  });

  it("prefers official_name, falls back to name, and tags source as plaid", () => {
    const withOfficial = mapPlaidAccount(account({ name: "checking", official_name: "Chase Total Checking" }));
    expect(withOfficial?.name).toBe("Chase Total Checking");
    expect(withOfficial?.source).toBe("plaid");

    const withoutOfficial = mapPlaidAccount(account({ name: "Plaid Checking", official_name: null }));
    expect(withoutOfficial?.name).toBe("Plaid Checking");
  });

  it("falls back to a placeholder mask when Plaid returns none", () => {
    expect(mapPlaidAccount(account({ mask: null }))?.last4).toBe("0000");
  });
});

describe("mapPlaidAccounts", () => {
  it("counts skipped accounts separately from mapped ones", () => {
    const { accounts, skipped } = mapPlaidAccounts([
      account({ account_id: "a", type: "depository", subtype: "checking" }),
      account({ account_id: "b", type: "loan", subtype: "mortgage" }),
      account({ account_id: "c", type: "credit", subtype: "credit card" }),
    ]);
    expect(accounts.map((a) => a.id)).toEqual(["a", "c"]);
    expect(skipped).toBe(1);
  });
});

describe("mapPlaidCategory", () => {
  it("maps high-confidence primary categories directly", () => {
    expect(mapPlaidCategory({ primary: "FOOD_AND_DRINK", detailed: "FOOD_AND_DRINK_RESTAURANT" })).toBe("Food");
    expect(mapPlaidCategory({ primary: "ENTERTAINMENT", detailed: "ENTERTAINMENT_SPORTING_EVENTS" })).toBe(
      "Entertainment",
    );
    expect(mapPlaidCategory({ primary: "INCOME", detailed: "INCOME_WAGES" })).toBe("Income");
  });

  it("prefers a specific detailed override over the broader primary bucket", () => {
    // A subscription is ENTERTAINMENT-adjacent under some detailed values,
    // but GENERAL_SERVICES_SUBSCRIPTION should win regardless of primary.
    expect(mapPlaidCategory({ primary: "GENERAL_SERVICES", detailed: "GENERAL_SERVICES_SUBSCRIPTION" })).toBe(
      "Subscriptions",
    );
    expect(
      mapPlaidCategory({ primary: "TRANSFER_OUT", detailed: "TRANSFER_OUT_INVESTMENT_AND_RETIREMENT_FUNDS" }),
    ).toBe("Investing");
    expect(mapPlaidCategory({ primary: "TRANSFER_OUT", detailed: "TRANSFER_OUT_SAVINGS" })).toBe("Savings");
  });

  it("falls back to Other for categories with no confident match, rather than guessing", () => {
    expect(mapPlaidCategory({ primary: "GENERAL_MERCHANDISE", detailed: "GENERAL_MERCHANDISE_OTHER" })).toBe(
      "Other",
    );
    expect(mapPlaidCategory({ primary: "MEDICAL", detailed: "MEDICAL_PRIMARY_CARE" })).toBe("Other");
    expect(mapPlaidCategory(null)).toBe("Other");
    expect(mapPlaidCategory(undefined)).toBe("Other");
  });
});

describe("mapPlaidTransaction", () => {
  it("flips Plaid's outflow-positive amount to this app's outflow-negative convention", () => {
    expect(mapPlaidTransaction(transaction({ amount: 14.2 })).amt).toBe(-14.2);
    // Plaid: negative = money in (e.g. a refund or payroll deposit) -> ours: positive
    expect(mapPlaidTransaction(transaction({ amount: -2150 })).amt).toBe(2150);
  });

  it("prefers merchant_name, falls back to the raw name field", () => {
    expect(mapPlaidTransaction(transaction({ merchant_name: "Chipotle", name: "CHIPOTLE 0123" })).merchant).toBe(
      "Chipotle",
    );
    expect(mapPlaidTransaction(transaction({ merchant_name: null, name: "CHIPOTLE 0123" })).merchant).toBe(
      "CHIPOTLE 0123",
    );
  });

  it("formats the ISO date to match the seed data's short display style", () => {
    expect(mapPlaidTransaction(transaction({ date: "2026-09-18" })).date).toBe("Sep 18");
  });

  it("tags the mapped transaction as plaid-sourced", () => {
    expect(mapPlaidTransaction(transaction({}))?.source).toBe("plaid");
  });
});
