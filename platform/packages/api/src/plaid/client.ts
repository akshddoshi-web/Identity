import { Configuration, PlaidApi, PlaidEnvironments } from "plaid";

/**
 * Defaults to Plaid's `sandbox` environment so the app is runnable locally
 * with fake institutions and no real bank credentials (per spec). Swap
 * PLAID_ENV to `development` or `production` with real credentials to go
 * live — see README "Swapping in production API keys".
 */
export function createPlaidClient(): PlaidApi {
  const env = (process.env.PLAID_ENV ?? "sandbox") as keyof typeof PlaidEnvironments;
  const configuration = new Configuration({
    basePath: PlaidEnvironments[env] ?? PlaidEnvironments.sandbox,
    baseOptions: {
      headers: {
        "PLAID-CLIENT-ID": process.env.PLAID_CLIENT_ID ?? "",
        "PLAID-SECRET": process.env.PLAID_SECRET ?? "",
      },
    },
  });
  return new PlaidApi(configuration);
}
