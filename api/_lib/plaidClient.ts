// Server-only. Never imported from src/ — see plaidMapping.ts's comment
// for why (Vercel's function bundler is separate from Vite's, so nothing
// under /api ever reaches the client bundle regardless, but the
// convention is kept strict on purpose).
import { Configuration, PlaidApi, PlaidEnvironments } from "plaid";

const PLAID_ENV = process.env.PLAID_ENV ?? "sandbox";

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `${name} is not set. Add it to .env locally (see README) and to the Vercel project's Environment Variables.`,
    );
  }
  return value;
}

export function getPlaidClient(): PlaidApi {
  const configuration = new Configuration({
    basePath: PlaidEnvironments[PLAID_ENV as keyof typeof PlaidEnvironments] ?? PlaidEnvironments.sandbox,
    baseOptions: {
      headers: {
        "PLAID-CLIENT-ID": requireEnv("PLAID_CLIENT_ID"),
        "PLAID-SECRET": requireEnv("PLAID_SECRET"),
      },
    },
  });
  return new PlaidApi(configuration);
}

/** Single fixed demo user — this app has no real auth system; every
 *  linked Item belongs to the one local user. */
export const PLAID_DEMO_CLIENT_USER_ID = "identity-demo-user";
