import type { VercelRequest, VercelResponse } from "@vercel/node";
import { getPlaidClient } from "../_lib/plaidClient";
import { mapPlaidAccounts, mapPlaidTransactions, type PlaidTransactionLike } from "../_lib/plaidMapping";

const MAX_SYNC_PAGES = 10; // safety cap, not a real limit for sandbox's demo history

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const publicToken = req.body?.public_token;
  if (typeof publicToken !== "string" || !publicToken) {
    return res.status(400).json({ error: "Missing public_token" });
  }

  try {
    const client = getPlaidClient();

    // access_token is a long-lived credential for this Item — it is
    // exchanged, used immediately below, and then never persisted or
    // returned to the client. This app has no server-side storage, so a
    // linked account can't be re-synced later without going through Link
    // again; that's a deliberate scope limit for this stage, not an
    // oversight (see README).
    const exchange = await client.itemPublicTokenExchange({ public_token: publicToken });
    const accessToken = exchange.data.access_token;

    const accountsResponse = await client.accountsGet({ access_token: accessToken });
    const { accounts, skipped } = mapPlaidAccounts(accountsResponse.data.accounts);

    const rawTransactions: PlaidTransactionLike[] = [];
    let cursor: string | undefined;
    for (let page = 0; page < MAX_SYNC_PAGES; page++) {
      const sync = await client.transactionsSync({ access_token: accessToken, cursor });
      rawTransactions.push(...sync.data.added);
      cursor = sync.data.next_cursor;
      if (!sync.data.has_more) break;
    }

    const transactions = mapPlaidTransactions(rawTransactions);

    return res.status(200).json({ accounts, transactions, skippedAccountCount: skipped });
  } catch (err) {
    console.error("exchange-public-token failed", err);
    const message = err instanceof Error ? err.message : "Unknown error";
    return res.status(500).json({ error: message });
  }
}
