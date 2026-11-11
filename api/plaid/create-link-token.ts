import type { VercelRequest, VercelResponse } from "@vercel/node";
import { CountryCode, Products } from "plaid";
import { getPlaidClient, PLAID_DEMO_CLIENT_USER_ID } from "../_lib/plaidClient";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const client = getPlaidClient();
    const response = await client.linkTokenCreate({
      user: { client_user_id: PLAID_DEMO_CLIENT_USER_ID },
      client_name: "Identity",
      products: [Products.Transactions],
      country_codes: [CountryCode.Us],
      language: "en",
    });
    return res.status(200).json({ link_token: response.data.link_token });
  } catch (err) {
    console.error("create-link-token failed", err);
    const message = err instanceof Error ? err.message : "Unknown error";
    return res.status(500).json({ error: message });
  }
}
