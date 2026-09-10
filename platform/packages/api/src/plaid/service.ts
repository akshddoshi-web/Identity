import { CountryCode, Products } from "plaid";
import { categorizeTransaction } from "@identity/shared";
import { prisma } from "../db";
import { decryptSecret, encryptSecret } from "../crypto";
import { createPlaidClient } from "./client";

const plaid = createPlaidClient();

export async function createLinkToken(userId: string): Promise<string> {
  const response = await plaid.linkTokenCreate({
    user: { client_user_id: userId },
    client_name: "Identity Platform",
    products: [Products.Transactions],
    country_codes: [CountryCode.Us],
    language: "en",
    webhook: process.env.PLAID_WEBHOOK_URL,
  });
  return response.data.link_token;
}

/**
 * Exchanges a Link `public_token` for a long-lived `access_token`, stores
 * the item + its accounts, and runs an initial transaction sync. Called
 * from the web app right after the Plaid Link flow succeeds.
 */
export async function exchangePublicTokenAndSync(userId: string, publicToken: string) {
  const exchange = await plaid.itemPublicTokenExchange({ public_token: publicToken });
  const accessToken = exchange.data.access_token;
  const plaidItemId = exchange.data.item_id;

  const accountsResponse = await plaid.accountsGet({ access_token: accessToken });
  const institutionName = accountsResponse.data.item.institution_id ?? "Unknown Institution";

  const item = await prisma.plaidItem.create({
    data: {
      userId,
      plaidItemId,
      accessTokenEncrypted: encryptSecret(accessToken),
      institutionName,
    },
  });

  for (const account of accountsResponse.data.accounts) {
    await prisma.financialAccount.create({
      data: {
        userId,
        plaidItemId: item.id,
        plaidAccountId: account.account_id,
        institutionName,
        name: account.name,
        type: mapPlaidAccountType(account.type),
        currentBalanceCents: Math.round((account.balances.current ?? 0) * 100),
        availableBalanceCents:
          account.balances.available !== null && account.balances.available !== undefined
            ? Math.round(account.balances.available * 100)
            : null,
        isLiability: account.type === "credit" || account.type === "loan",
      },
    });
  }

  await syncTransactionsForItem(item.id);
  return item;
}

function mapPlaidAccountType(
  plaidType: string,
): "checking" | "savings" | "credit" | "investment" | "loan" {
  switch (plaidType) {
    case "depository":
      return "checking";
    case "credit":
      return "credit";
    case "investment":
      return "investment";
    case "loan":
      return "loan";
    default:
      return "checking";
  }
}

/**
 * Pulls the transaction delta since the item's last stored cursor using
 * Plaid's `/transactions/sync` endpoint (the recommended replacement for
 * polling `/transactions/get`). Invoked by the Plaid webhook handler on
 * SYNC_UPDATES_AVAILABLE, and once right after Link for the initial pull.
 */
export async function syncTransactionsForItem(plaidItemDbId: string): Promise<void> {
  const item = await prisma.plaidItem.findUniqueOrThrow({ where: { id: plaidItemDbId } });
  const accessToken = decryptSecret(item.accessTokenEncrypted);
  const accounts = await prisma.financialAccount.findMany({ where: { plaidItemId: item.id } });
  const accountByPlaidId = new Map(accounts.map((a) => [a.plaidAccountId, a]));

  const userRules = await prisma.categorizationRule.findMany({ where: { userId: item.userId } });

  let cursor = item.transactionsCursor ?? undefined;
  let hasMore = true;

  while (hasMore) {
    const response = await plaid.transactionsSync({ access_token: accessToken, cursor });

    for (const tx of [...response.data.added, ...response.data.modified]) {
      const account = accountByPlaidId.get(tx.account_id);
      if (!account) continue;

      const category = categorizeTransaction(
        { merchantName: tx.merchant_name ?? tx.name, plaidCategory: tx.personal_finance_category?.primary ?? null },
        userRules.map((r) => ({ pattern: r.pattern, category: r.category })),
      );

      await prisma.transaction.upsert({
        where: { plaidTransactionId: tx.transaction_id },
        create: {
          accountId: account.id,
          plaidTransactionId: tx.transaction_id,
          merchantName: tx.merchant_name ?? tx.name,
          amountCents: Math.round(tx.amount * 100),
          category,
          postedAt: new Date(tx.date),
          isPending: tx.pending,
        },
        update: {
          amountCents: Math.round(tx.amount * 100),
          isPending: tx.pending,
        },
      });
    }

    for (const removed of response.data.removed) {
      if (!removed.transaction_id) continue;
      await prisma.transaction.deleteMany({ where: { plaidTransactionId: removed.transaction_id } });
    }

    cursor = response.data.next_cursor;
    hasMore = response.data.has_more;
  }

  await prisma.plaidItem.update({ where: { id: item.id }, data: { transactionsCursor: cursor } });
}

export async function findPlaidItemByPlaidItemId(plaidItemId: string) {
  return prisma.plaidItem.findUnique({ where: { plaidItemId } });
}
