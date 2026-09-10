import { findPlaidItemByPlaidItemId, syncTransactionsForItem } from "@identity/api";

/**
 * Plaid webhook receiver — transaction updates are pushed here rather than
 * polled. Configure PLAID_WEBHOOK_URL (e.g. an ngrok tunnel in dev) to this
 * route's public URL so Plaid can reach it.
 *
 * Signature verification is intentionally omitted for sandbox/dev use;
 * verify the `Plaid-Verification` JWT header before trusting this in
 * production (see https://plaid.com/docs/api/webhooks/webhook-verification/).
 */
export async function POST(req: Request) {
  const body = (await req.json()) as { webhook_type?: string; webhook_code?: string; item_id?: string };

  if (body.webhook_type === "TRANSACTIONS" && body.webhook_code === "SYNC_UPDATES_AVAILABLE" && body.item_id) {
    const item = await findPlaidItemByPlaidItemId(body.item_id);
    if (item) {
      await syncTransactionsForItem(item.id);
    }
  }

  return Response.json({ received: true });
}
